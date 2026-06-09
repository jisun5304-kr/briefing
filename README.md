
# 시황 브리핑 (briefing)

한국·미국 시장 시황을 날짜·시간대별로 보여주는 정적 사이트입니다.
👉 https://jisun5304-kr.github.io/briefing/

## 운영 방식 — 완전 자동 (GitHub Actions)

평일 하루 3회(🌅 오전 07:30 / ☀️ 오후 16:00 / 🌙 밤 23:00 KST) GitHub Actions가
**시장 데이터 수집 → AI 해설 작성 → HTML 생성 → 자동 배포**합니다. PC를 켤 필요가 없습니다.

- 상세: [AUTOMATION.md](AUTOMATION.md)
- 안전장치: 지수·환율 **숫자는 코드가 수집한 실제 값만** 사용하고, AI는 해설 텍스트만 작성합니다.

## 구조

| 경로 | 역할 |
|---|---|
| `index.html` | 메인 화면 (목록·인증·테마·iframe 로더) |
| `briefings/` | 개별 브리핑 HTML + `manifest.json` (자동화가 갱신) |
| `templates/briefing.html` | 브리핑 디자인 템플릿 |
| `scripts/` | 데이터 수집·해설·렌더·manifest 생성 스크립트 |
| `.github/workflows/` | 자동 생성(`briefing.yml`)·과거 보정(`backfill.yml`) |

## 코드 수정 방법

운영은 클라우드가 하므로 로컬 클론 없이 **웹에서 수정**합니다.

1. 이 레포에서 짧은 브랜치 생성
2. 파일 수정 (주로 `scripts/PROSE_INSTRUCTIONS.md`, `index.html`, `templates/briefing.html`)
3. Pull Request → `main` 병합 → GitHub Pages 자동 재배포

> 봇이 `briefings/`를, 사람이 그 외를 수정하므로 충돌은 드뭅니다.
> 
