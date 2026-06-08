# -*- coding: utf-8 -*-
"""
render_briefing.py — build/input.json(숫자) + build/prose.json(해설) → 최종 브리핑 HTML

핵심: 숫자는 input.json(코드 수집)에서만 가져온다.
prose.json(LLM 작성)은 해설 텍스트와 지수별 한 줄 설명(note)만 제공하며,
지수 값/등락률은 절대 prose에서 읽지 않는다 → AI가 숫자를 바꿀 수 없음.
"""
import os
import re
import json
import sys

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(ROOT, "build")
TEMPLATE_DIR = os.path.join(ROOT, "templates")
BRIEFINGS_DIR = os.path.join(ROOT, "briefings")

BAR_MAP = {"up": "bar-up", "down": "bar-down", "flat": "bar-warn"}


def log(msg):
    print(f"[render] {msg}", flush=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    inp = load_json(os.path.join(BUILD_DIR, "input.json"))

    prose_path = os.path.join(BUILD_DIR, "prose.json")
    if not os.path.exists(prose_path):
        log("!! build/prose.json 없음 — Claude 해설 생성 단계가 실패했습니다.")
        sys.exit(1)

    raw = open(prose_path, "r", encoding="utf-8").read().strip()
    # 혹시 코드펜스(```json ... ```)로 감싸여 오면 벗겨냄
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        prose = json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"!! prose.json 파싱 실패: {e}")
        sys.exit(1)

    # ── 지수: 숫자는 input에서, note만 prose에서 병합 ──
    notes = prose.get("index_notes", {}) or {}
    indices = []
    for x in inp["indices"]:
        x = dict(x)
        x["note"] = notes.get(x["name"], "")
        indices.append(x)

    sentiment = (prose.get("sentiment") or "flat").lower()
    header_bar = BAR_MAP.get(sentiment, "bar-info")

    # ── 섹터: 방향성을 CSS 클래스로 정규화 (flat→warn, 기존 디자인 규칙) ──
    TXT_CLASS = {"up": "up", "down": "down", "flat": "warn"}
    sectors = []
    for s in (prose.get("sectors") or []):
        s = dict(s)
        s["css"] = TXT_CLASS.get((s.get("direction") or "flat").lower(), "warn")
        sectors.append(s)

    # ── 필수 해설 필드 검증 ──
    for key in ("headline", "summary", "drivers", "sectors", "checklist"):
        if not prose.get(key):
            log(f"!! prose.json 필수 항목 누락: {key}")
            sys.exit(1)

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("briefing.html")
    html = tmpl.render(
        session_emoji=inp["session_emoji"],
        session_ko=inp["session_ko"],
        session_time=inp["session_time"],
        session_basis=inp["session_basis"],
        date_short=inp["date_short"],
        generated_at_kst=inp["generated_at_kst"],
        header_bar=header_bar,
        backfill=inp.get("backfill", False),
        headline=prose["headline"],
        summary=prose["summary"],
        watch_points=prose.get("watch_points", ""),
        indices=indices,
        drivers=prose["drivers"],
        sectors=sectors,
        checklist=prose["checklist"],
    )

    os.makedirs(BRIEFINGS_DIR, exist_ok=True)
    fname = f"{inp['date_us']}_{inp['session']}.html"
    out_path = os.path.join(BRIEFINGS_DIR, fname)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"브리핑 생성 완료 → briefings/{fname}")


if __name__ == "__main__":
    main()
