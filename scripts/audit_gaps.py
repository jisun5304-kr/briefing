# -*- coding: utf-8 -*-
"""
audit_gaps.py — 최근 평일들의 세션 결번을 점검해 리포트 출력.

판단 근거는 briefings/manifest.json(= build_manifest.py가 내용검증까지 반영한 결과).
각 '거래일'은 ready 세션 3개(오전·오후·밤)가 정상.
- 주말(토·일) 제외
- scripts/holidays.txt 에 적힌 휴장일 제외(한 줄에 YYYY-MM-DD, # 주석 허용)
결번이 있으면 GITHUB_OUTPUT 에 has_gaps=true + report 를 기록한다(워크플로우가 이슈로 알림).
audit 스텝 자체는 항상 성공(exit 0) — 알림은 다음 스텝이 조건부로 처리.
"""
import os
import json
import sys
from datetime import datetime, timezone, timedelta, date

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "briefings", "manifest.json")
HOLIDAYS = os.path.join(ROOT, "scripts", "holidays.txt")
LOOKBACK_DAYS = 10            # 오늘 기준 최근 며칠을 훑을지
PERIODS = ("오전", "오후", "밤")


def load_holidays():
    if not os.path.exists(HOLIDAYS):
        return set()
    out = set()
    with open(HOLIDAYS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.add(line[:10])
    return out


def today_kst():
    # 테스트·수동 점검용 오버라이드
    override = (os.environ.get("AUDIT_TODAY") or "").strip()
    if override:
        return date.fromisoformat(override)
    return datetime.now(KST).date()


def emit_output(has_gaps, report):
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if not gh_out:
        return
    with open(gh_out, "a", encoding="utf-8") as f:
        f.write(f"has_gaps={'true' if has_gaps else 'false'}\n")
        f.write("report<<AUDIT_EOF\n" + report + "\nAUDIT_EOF\n")


def main():
    if not os.path.exists(MANIFEST):
        print("manifest.json 없음 — 점검 불가")
        emit_output(False, "manifest.json 없음")
        return
    data = json.load(open(MANIFEST, encoding="utf-8-sig"))  # BOM 있어도 안전
    by_date = {d["date"]: d for d in data}
    holidays = load_holidays()
    today = today_kst()

    gaps = []
    for i in range(1, LOOKBACK_DAYS + 1):
        day = today - timedelta(days=i)
        if day.weekday() >= 5:           # 토(5)·일(6)
            continue
        ds = day.isoformat()
        if ds in holidays:               # 휴장일
            continue
        entry = by_date.get(ds)
        ready = {s["period"] for s in entry["sessions"] if s.get("ready")} if entry else set()
        missing = [p for p in PERIODS if p not in ready]
        if missing:
            gaps.append((ds, missing))

    if not gaps:
        msg = f"최근 {LOOKBACK_DAYS}일 평일(휴장 제외) 결번 없음 ✅"
        print(msg)
        emit_output(False, msg)
        return

    lines = [f"최근 {LOOKBACK_DAYS}일 내 **결번 {len(gaps)}건** (주말·holidays.txt 제외):", ""]
    for ds, missing in sorted(gaps):
        lines.append(f"- `{ds}` — 누락: {', '.join(missing)}")
    report = "\n".join(lines)
    print(report)
    emit_output(True, report)


if __name__ == "__main__":
    main()
