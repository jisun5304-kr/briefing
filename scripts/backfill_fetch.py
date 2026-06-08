# -*- coding: utf-8 -*-
"""
backfill_fetch.py — 과거 날짜 구간의 '실제' 지수·환율 종가로 세션별 input.json 생성.

정직형 백필: 숫자는 yfinance 과거 데이터(실제값). 뉴스는 과거 소급 수집이 불가능하므로
수집하지 않으며(news=[]), 해설은 가격 흐름에 근거해서만 작성하도록 한다(backfill=True 플래그).
이미 존재하는 브리핑 파일은 건드리지 않는다(덮어쓰기 금지).
"""
import os
import json
from datetime import date, timedelta

# 기존 수집 스크립트의 헬퍼 재사용 (import 시 main()은 실행되지 않음)
from fetch_market import (
    INDEX_SPECS, WEEKDAY_KO, fmt_value, classify,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFINGS_DIR = os.path.join(ROOT, "briefings")
OUT_DIR = os.path.join(ROOT, "build", "backfill")

SESSIONS = [
    {"key": "morning",   "ko": "오전", "emoji": "🌅", "time": "07:30"},
    {"key": "afternoon", "ko": "오후", "emoji": "☀️", "time": "16:00"},
    {"key": "night",     "ko": "밤",   "emoji": "🌙", "time": "23:00"},
]

START = os.environ.get("START_DATE", "2026-05-25")
END = os.environ.get("END_DATE", "2026-06-08")


def log(m):
    print(f"[backfill] {m}", flush=True)


def load_series():
    """각 티커의 {date: close} 시계열을 구간보다 약간 넓게 가져온다."""
    import yfinance as yf
    s = date.fromisoformat(START) - timedelta(days=14)
    e = date.fromisoformat(END) + timedelta(days=2)
    series = {}
    for spec in INDEX_SPECS:
        t = spec["ticker"]
        try:
            hist = yf.Ticker(t).history(start=s.isoformat(), end=e.isoformat(), auto_adjust=False)
            m = {}
            for ts, row in hist.iterrows():
                c = row["Close"]
                if c == c:  # NaN 제외
                    m[ts.date()] = float(c)
            series[t] = m
            log(f"  {spec['name']}: {len(m)}거래일 로드")
        except Exception as ex:
            series[t] = {}
            log(f"  ! {t} 과거데이터 실패: {ex}")
    return series


def as_of(daymap, d):
    """날짜 d 시점의 (값, 직전값). d 당일이 없으면 d 이전 최근 거래일 기준."""
    days = sorted(k for k in daymap if k <= d)
    if not days:
        return None, None
    val = daymap[days[-1]]
    prev = daymap[days[-2]] if len(days) >= 2 else None
    return val, prev


def build_index_cards(series, d):
    cards = []
    for spec in INDEX_SPECS:
        val, prev = as_of(series.get(spec["ticker"], {}), d)
        pct = (val - prev) / prev * 100 if (val is not None and prev) else None
        direction, label = classify(pct)
        cards.append({
            "name": spec["name"],
            "value": fmt_value(val),
            "change_pct": round(pct, 2) if pct is not None else None,
            "change_label": label,
            "direction": direction,
        })
    return cards


def main():
    series = load_series()
    kospi_dates = set(series.get("^KS11", {}).keys())  # 한국 거래일 판별 기준

    os.makedirs(OUT_DIR, exist_ok=True)
    start_d = date.fromisoformat(START)
    end_d = date.fromisoformat(END)

    made = 0
    d = start_d
    while d <= end_d:
        if d not in kospi_dates:  # 주말·휴장일 자동 스킵
            d += timedelta(days=1)
            continue

        date_us = d.strftime("%Y_%m_%d")
        date_label = f"{d.year}년 {d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})"
        date_short = f"{d.month}/{d.day} ({WEEKDAY_KO[d.weekday()]})"
        cards = build_index_cards(series, d)

        for sess in SESSIONS:
            html_path = os.path.join(BRIEFINGS_DIR, f"{date_us}_{sess['key']}.html")
            if os.path.exists(html_path):
                continue  # 이미 있는 브리핑은 건드리지 않음

            payload = {
                "session": sess["key"],
                "session_ko": sess["ko"],
                "session_emoji": sess["emoji"],
                "session_time": sess["time"],
                "session_basis": f"{d.isoformat()} 종가 기준 · 사후 보정",
                "date_iso": d.isoformat(),
                "date_us": date_us,
                "date_label": date_label,
                "date_short": date_short,
                "generated_at_kst": "사후 보정",
                "backfill": True,
                "indices": cards,
                "news": [],
            }
            out = os.path.join(OUT_DIR, f"{date_us}_{sess['key']}.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            made += 1
        d += timedelta(days=1)

    log(f"생성 대상 input {made}건 → {OUT_DIR}")
    if made == 0:
        log("채울 세션이 없습니다(이미 전부 존재하거나 거래일 없음).")


if __name__ == "__main__":
    main()
