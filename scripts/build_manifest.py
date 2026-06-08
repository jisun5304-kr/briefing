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
        days[date_key]["sessions"].append({
            "time": info["time"],
            "emoji": info["emoji"],
            "period": info["period"],
            "ready": True,
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
    print(f"[manifest] {len(result)}일 / {total}개 세션 반영 → {out_path}", flush=True)


if __name__ == "__main__":
    main()
