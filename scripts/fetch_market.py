# -*- coding: utf-8 -*-
"""
fetch_market.py — 실제 시장 데이터(지수·환율) + 뉴스 수집 → build/input.json

설계 원칙: 숫자는 전부 여기서(코드) 실제 데이터로 채운다.
LLM은 이 input.json을 '재료'로 받아 해설만 쓴다. 숫자는 절대 LLM이 만들지 않는다.

- 지수/환율: yfinance (무료, API 키 불필요)
- 뉴스: 네이버 검색 API(키 있으면) + RSS(항상) 하이브리드, 중복 제거 후 병합
"""
import os
import re
import json
import sys
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(ROOT, "build")

# ── 지수/환율 정의 (표시명, yfinance 티커) ──
INDEX_SPECS = [
    {"name": "S&P 500",  "ticker": "^GSPC"},
    {"name": "나스닥",    "ticker": "^IXIC"},
    {"name": "다우존스",  "ticker": "^DJI"},
    {"name": "코스피",    "ticker": "^KS11"},
    {"name": "코스닥",    "ticker": "^KQ11"},
    {"name": "USD/KRW",  "ticker": "KRW=X"},
]

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]  # Monday=0

# ── 세션별 뉴스 검색 키워드 ──
COMMON_KEYWORDS = ["코스피", "코스닥", "환율", "외국인 수급", "반도체"]
SESSION_KEYWORDS = {
    "morning":   ["뉴욕증시", "나스닥", "미국 증시", "연준", "삼성전자"],
    "afternoon": ["코스피 마감", "장중 시황", "삼성전자", "SK하이닉스", "코스닥"],
    "night":     ["미국 증시 개장", "유럽 증시", "국제유가", "환율"],
}
SESSION_META = {
    "morning":   {"ko": "오전", "emoji": "🌅", "time": "07:30",
                  "basis": "밤사이 미국 증시 마감 기준"},
    "afternoon": {"ko": "오후", "emoji": "☀️", "time": "16:00",
                  "basis": "국내 장중·마감 기준"},
    "night":     {"ko": "밤",   "emoji": "🌙", "time": "23:00",
                  "basis": "미국 장 개장·유럽 기준"},
}

# ── RSS 뉴스 소스 (키 불필요, 항상 동작) ──
RSS_FEEDS = [
    "https://www.yna.co.kr/rss/economy.xml",          # 연합뉴스 경제
    "https://www.mk.co.kr/rss/30100041/",             # 매일경제 증권
    "https://rss.hankyung.com/feed/economy.xml",      # 한국경제 경제
]


def log(msg):
    print(f"[fetch] {msg}", flush=True)


# ─────────────────────────────────────────────
# 1. 세션·날짜 결정
# ─────────────────────────────────────────────
def resolve_session():
    """SESSION 환경변수가 있으면 그걸, 없으면 KST 시각으로 추정."""
    s = (os.environ.get("SESSION") or "").strip().lower()
    if s in SESSION_META:
        return s
    hour = datetime.now(KST).hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 20:
        return "afternoon"
    return "night"


# ─────────────────────────────────────────────
# 2. 지수·환율 (yfinance)
# ─────────────────────────────────────────────
def fmt_value(v):
    if v is None:
        return "N/A"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def classify(pct):
    if pct is None:
        return "flat", "—"
    if pct >= 0.05:
        return "up", f"▲ +{pct:.2f}%"
    if pct <= -0.05:
        return "down", f"▼ {pct:.2f}%"  # pct가 음수라 부호 포함
    return "flat", f"{pct:+.2f}%"


def fetch_quote(ticker):
    """최근 2거래일 종가로 (현재값, 등락률%) 반환. 실패 시 (None, None)."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="7d", auto_adjust=False)
        closes = [c for c in hist["Close"].tolist() if c == c]  # NaN 제거
        if len(closes) >= 2:
            last, prev = closes[-1], closes[-2]
            pct = (last - prev) / prev * 100 if prev else None
            return float(last), pct
        if len(closes) == 1:
            return float(closes[-1]), None
    except Exception as e:
        log(f"  ! {ticker} 조회 실패: {e}")
    return None, None


def fetch_indices():
    out = []
    for spec in INDEX_SPECS:
        val, pct = fetch_quote(spec["ticker"])
        direction, change_label = classify(pct)
        out.append({
            "name": spec["name"],
            "value": fmt_value(val),
            "change_pct": round(pct, 2) if pct is not None else None,
            "change_label": change_label,
            "direction": direction,
        })
        log(f"  {spec['name']}: {fmt_value(val)} {change_label}")
        time.sleep(0.3)  # 야후 레이트리밋 완화
    return out


# ─────────────────────────────────────────────
# 3. 뉴스 (네이버 API + RSS 하이브리드)
# ─────────────────────────────────────────────
def _strip_tags(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return (text.replace("&quot;", '"').replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
                .strip())


def fetch_naver_news(keywords):
    cid = os.environ.get("NAVER_CLIENT_ID")
    csec = os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and csec):
        log("  네이버 키 없음 → RSS만 사용")
        return []
    items = []
    for kw in keywords:
        try:
            url = ("https://openapi.naver.com/v1/search/news.json?display=5&sort=date&query="
                   + urllib.parse.quote(kw))
            req = urllib.request.Request(url, headers={
                "X-Naver-Client-Id": cid,
                "X-Naver-Client-Secret": csec,
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            for it in data.get("items", []):
                items.append({
                    "title": _strip_tags(it.get("title")),
                    "source": "naver",
                    "keyword": kw,
                })
        except Exception as e:
            log(f"  ! 네이버 '{kw}' 실패: {e}")
        time.sleep(0.2)
    log(f"  네이버 뉴스 {len(items)}건 수집")
    return items


def fetch_rss_news():
    items = []
    for feed in RSS_FEEDS:
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = r.read()
            root = ET.fromstring(raw)
            for item in root.iter("item"):
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    items.append({
                        "title": _strip_tags(title_el.text),
                        "source": "rss",
                        "keyword": None,
                    })
        except Exception as e:
            log(f"  ! RSS {feed} 실패: {e}")
    log(f"  RSS 뉴스 {len(items)}건 수집")
    return items


def _norm(t):
    return re.sub(r"\s+", "", re.sub(r"[^\w가-힣]", "", t or "")).lower()


def merge_news(*lists, limit=14):
    """제목 정규화로 중복 제거 후 병합. 네이버 우선."""
    seen, merged = set(), []
    for lst in lists:
        for it in lst:
            key = _norm(it["title"])
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(it)
    return merged[:limit]


# ─────────────────────────────────────────────
# 4. 조립 & 저장
# ─────────────────────────────────────────────
def main():
    session = resolve_session()
    meta = SESSION_META[session]
    now = datetime.now(KST)

    # ── 논리적 '브리핑 날짜' 결정 (벽시계와 분리) ──
    # 밤(23:00) 작업이 GitHub Actions 지연으로 자정을 넘겨 실행되면
    # datetime.now(KST)는 다음날이 되어, 전날 밤 브리핑이 다음날 날짜로 오기록된다.
    # → 새벽(05시 이전)에 실행된 밤 세션은 '전날 밤'으로 되돌린다.
    #   (오전 07:30·오후 16:00은 자정과 멀어 영향 없음)
    biz = now
    if session == "night" and now.hour < 5:
        biz = now - timedelta(days=1)
        log(f"밤 세션이 자정 이후({now:%H:%M}) 실행 → 날짜를 전날({biz:%Y-%m-%d})로 보정")

    date_iso = biz.strftime("%Y-%m-%d")
    date_us = biz.strftime("%Y_%m_%d")
    date_label = f"{biz.year}년 {biz.month}월 {biz.day}일 ({WEEKDAY_KO[biz.weekday()]})"
    date_short = f"{biz.month}/{biz.day} ({WEEKDAY_KO[biz.weekday()]})"

    log(f"세션={session} 날짜={date_iso} (실제 실행 {now:%Y-%m-%d %H:%M} KST)")

    indices = fetch_indices()

    keywords = SESSION_KEYWORDS.get(session, []) + COMMON_KEYWORDS
    news = merge_news(fetch_naver_news(keywords), fetch_rss_news())

    payload = {
        "session": session,
        "session_ko": meta["ko"],
        "session_emoji": meta["emoji"],
        "session_time": meta["time"],
        "session_basis": meta["basis"],
        "date_iso": date_iso,
        "date_us": date_us,
        "date_label": date_label,
        "date_short": date_short,
        "generated_at_kst": now.strftime("%Y-%m-%d %H:%M"),
        "indices": indices,
        "news": news,
    }

    os.makedirs(BUILD_DIR, exist_ok=True)
    out_path = os.path.join(BUILD_DIR, "input.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(f"저장 완료 → {out_path} (지수 {len(indices)}, 뉴스 {len(news)})")

    # 지수가 전부 N/A면 실패로 간주 (데이터 소스 장애)
    if all(i["value"] == "N/A" for i in indices):
        log("!! 모든 지수 조회 실패 — 데이터 소스 점검 필요")
        sys.exit(1)


if __name__ == "__main__":
    main()

