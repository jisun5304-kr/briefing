# -*- coding: utf-8 -*-
"""
build_manifest.py — briefings/*.html 스캔 → briefings/manifest.json 생성
(기존 update.ps1 의 manifest 생성 로직을 Python으로 포팅. index.html이 이 파일을 읽는다.)
"""
import os
import re
import json
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFINGS_DIR = os.path.join(ROOT, "briefings")

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]  # Monday=0
PERIOD_MAP = {
    "morning":   {"period": "오전", "emoji": "🌅", "time": "07:30", "order": 0},
    "afternoon": {"period": "오후", "emoji": "☀️", "time": "16:00", "order": 1},
    "night":     {"period": "밤",   "emoji": "🌙", "time": "23:00", "order": 2},
}
PAT = re.compile(r"^(\d{4})_(\d{2})_(\d{2})_(morning|afternoon|night)\.html$")

# 유효한 브리핑으로 인정할 최소 조건(빈/깨진/플레이스홀더 파일이 ready로 새는 것 차단)
MIN_BYTES = 1500


def is_valid_briefing(path):
    """렌더가 정상 완료된 브리핑인지 가볍게 검증. 실패 시 ready=false 처리."""
    try:
        if os.path.getsize(path) < MIN_BYTES:
            return False
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        # 모든 정상 브리핑은 템플릿 푸터(disclaimer)와 닫는 태그를 포함한다
        return ("disclaimer" in html) and ("</html>" in html)
    except OSError:
        return False


def main():
    days = {}
    for name in os.listdir(BRIEFINGS_DIR):
        m = PAT.match(name)
        if not m:
            continue
        y, mo, d, period = m.group(1), m.group(2), m.group(3), m.group(4)
        date_key = f"{y}-{mo}-{d}"
        if date_key not in days:
            dt = date(int(y), int(mo), int(d))
            label = f"{int(y)}년 {int(mo)}월 {int(d)}일 ({WEEKDAY_KO[dt.weekday()]})"
            days[date_key] = {"date": date_key, "label": label, "sessions": []}
        info = PERIOD_MAP[period]
        ready = is_valid_briefing(os.path.join(BRIEFINGS_DIR, name))
        if not ready:
            print(f"[manifest] ⚠ 유효성 실패 → ready=false: {name}", flush=True)
        days[date_key]["sessions"].append({
            "time": info["time"],
            "emoji": info["emoji"],
            "period": info["period"],
            "ready": ready,
            "file": f"briefings/{name}",
            "_order": info["order"],
        })

    # 세션 정렬(오전→오후→밤) 후 내부 정렬키 제거, 날짜 오름차순
    result = []
    for date_key in sorted(days.keys()):
        day = days[date_key]
        day["sessions"].sort(key=lambda s: s.pop("_order"))
        result.append(day)

    out_path = os.path.join(BRIEFINGS_DIR, "manifest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    total = sum(len(d["sessions"]) for d in result)
    ready_n = sum(1 for d in result for s in d["sessions"] if s["ready"])
    print(f"[manifest] {len(result)}일 / 세션 {total}개(ready {ready_n}, 무효 {total-ready_n}) → {out_path}", flush=True)


if __name__ == "__main__":
    main()

