# 시황 브리핑 자동화 (GitHub Actions)

5월 25일 이후 멈춰 있던 수동 작업을 **완전 자동화**로 교체한 구성입니다.
하루 3회(오전 07:30 / 오후 16:00 / 밤 23:00 KST) GitHub Actions가 클라우드에서
**실제 시장 데이터를 수집 → AI가 해설 작성 → HTML 생성 → 자동 배포**합니다. PC를 켜둘 필요가 없습니다.

## 동작 원리 — "숫자는 코드, 해설은 AI"

```
GitHub Actions (cron 3회/일)
  │
  ├─ ① fetch_market.py   실제 데이터 수집 → build/input.json
  │        지수·환율: yfinance (S&P500·나스닥·다우·코스피·코스닥·USD/KRW)
  │        뉴스: 네이버 검색 API + 연합/매경/한경 RSS (하이브리드, 중복 제거)
  │
  ├─ ② Claude Code       input.json을 읽고 해설만 작성 → build/prose.json
  │        (지수 숫자는 절대 건드리지 않음. 해설·전망·관전포인트만)
  │
  ├─ ③ render_briefing.py  숫자(input) + 해설(prose)를 템플릿에 결합
  │        → briefings/YYYY_MM_DD_session.html   ※숫자는 코드값만 주입
  │
  ├─ ④ build_manifest.py   briefings/ 스캔 → manifest.json 재생성
  │
  └─ ⑤ git commit & push   → GitHub Pages 자동 배포
```

**핵심 안전장치**: 지수·환율 수치는 ①에서 수집한 실제 값만 ③에서 주입됩니다.
AI(②)는 해설 텍스트와 지수별 한 줄 코멘트만 쓰고, 숫자 필드 자체에 접근하지 않습니다.
→ **수치 정확도 100% 보장.**

## 최초 1회 설정 (본인이 직접)

### 1. Claude 구독 토큰 발급
로컬 터미널(이 PC)에서:
```bash
claude setup-token
```
브라우저 로그인 후 출력되는 **1년짜리 토큰**을 복사해 둡니다. (Pro/Max 구독 필요, 추가 과금 없음)

### 2. GitHub Secrets 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret** 에서:

| Secret 이름 | 값 | 필수 |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | 위 1번에서 복사한 토큰 | ✅ 필수 |
| `NAVER_CLIENT_ID` | 네이버 검색 API Client ID | 선택(없으면 RSS만) |
| `NAVER_CLIENT_SECRET` | 네이버 검색 API Secret | 선택 |

> 네이버 키는 [developers.naver.com](https://developers.naver.com/apps/#/register) → 앱 등록 → "검색" API 추가로 5분이면 발급(무료, 일 25,000건). 없어도 RSS 뉴스로 동작합니다.

### 3. Actions 쓰기 권한 확인
저장소 → **Settings → Actions → General → Workflow permissions** → **"Read and write permissions"** 선택.
(자동 push에 필요. `GITHUB_TOKEN`이 커밋을 올립니다.)

### 4. 첫 테스트 (수동 실행)
저장소 → **Actions → "시황 브리핑 자동 생성" → Run workflow** → 세션 선택 후 실행.
로그를 보며 정상 동작을 확인합니다. 성공하면 cron이 자동으로 하루 3회 돌립니다.

## 스케줄

| 세션 | KST | UTC cron |
|---|---|---|
| 🌅 오전 | 07:30 | `30 22 * * 0-4` |
| ☀️ 오후 | 16:00 | `0 7 * * 1-5` |
| 🌙 밤 | 23:00 | `0 14 * * 1-5` |

> GitHub Actions cron은 분 단위로 정확하지 않고 수 분 지연될 수 있습니다(정상). 평일만 실행됩니다.

## 파일 구조

```
.github/workflows/briefing.yml   # 자동화 워크플로우
scripts/
  fetch_market.py                # ① 데이터 수집
  PROSE_INSTRUCTIONS.md          # ② Claude 해설 작성 지침
  render_briefing.py             # ③ HTML 생성
  build_manifest.py              # ④ manifest 생성 (기존 update.ps1 대체)
templates/briefing.html          # 브리핑 디자인 템플릿
requirements.txt                 # yfinance, jinja2
build/                           # 실행 중 생성되는 중간 산출물 (input.json, prose.json)
```

## 수동 운영 (기존 방식도 유지)

기존 `update.bat`(로컬에서 직접 HTML 넣고 더블클릭)도 그대로 둡니다.
자동화와 별개로, 손으로 특정 브리핑을 추가하고 싶을 때 쓸 수 있습니다.

## 비용

- yfinance · RSS: 무료
- 네이버 검색 API: 무료(일 25,000건 한도 내)
- Claude Code: **구독에 포함된 무인 실행 크레딧 내(월 약 $1 사용, Pro 기준 $20 한도)** → 사실상 추가 비용 0
- GitHub Actions: 퍼블릭 저장소는 무료
