# Works Log — the-last-of-us-stock

> 이 파일은 프로젝트의 작업 이력을 시간 순서로 기록합니다.
> 새 작업이 완료될 때마다 아래에 항목을 추가합니다.

---

## 2026-06-11

### 21:10 — 라오어 무한매수법 조사 및 plan-opus.md 작성
- 라오어 무한매수법 관련 자료 수집 (나무위키, skystone.tistory, 튜레이터, 라다차 등)
- 유튜브 채널 [@laofus](https://www.youtube.com/@laofus) 분석
- `plan-opus.md` 작성
  - 무한매수법 정의·철학·핵심 위험 정리
  - V1 / V2 / V2.1 / V2.2 버전별 매수·매도 규칙 상세 정리
  - 종목 선정 기준 (거래량·RSI·상관관계)
  - 백테스트 설계 방향 및 평가 지표 정의

### 21:20 — plan-opus.md 확장 (VOO·QQQ·한국 ETF·구간·대시보드 추가)
- 백테스트 종목 유니버스 확장
  - 미국: VOO, QQQ (1x 벤치마크) + SPXL, UPRO (3x 레버리지)
  - 한국: KODEX 200 (069500.KS), KODEX 레버리지 (122630.KS), KODEX 코스닥150 (229200.KS), KODEX 코스닥150 레버리지 (233740.KS)
- 백테스트 구간 추가: 최근 3년, 최근 5년 (롤링)
- HTML 대시보드 계획 추가 (8장): Bootstrap 5 + Plotly.js 정적 HTML
- 기존 `stock_candle` 페이지 보존 원칙 명시
- nginx `infinite_buying/` 별도 경로 배포 설계

### 21:46 — 전체 구현 (백테스트 엔진 + 대시보드)
- **프로젝트 구조 생성** (`src/lastofus/` 패키지)
- **`src/lastofus/config.py`**: 9개 티커 설정, 6개 기간 정의, TICKER_GROUPS
- **`src/lastofus/data/loader.py`**: yfinance 다운로드, parquet 캐시, 한국 티커 오류 처리
- **`src/lastofus/core/account.py`**: Account 데이터클래스 (buy/sell/reset_cycle/equity)
- **`src/lastofus/strategy/infinite_v22.py`**: V2.2 전략 구현
  - 전반전(≤50%): 이중 LOC (평단가 / 평단가×1.05)
  - 후반전(>50%): 보수적 단일 LOC (평단가 이하만)
  - 40회 소진 시 쿼터컷 (25% 매도 → 시드 재확보)
  - 벤치마크: `run_bah()` (Buy & Hold), `run_dca()` (적립식 40회 균등)
- **`src/lastofus/backtest/engine.py`**: 전체 종목×구간 실행 오케스트레이션
- **`src/lastofus/backtest/metrics.py`**: CAGR, MDD, Sharpe, Sortino 산출
- **`src/lastofus/backtest/report.py`**: 결과 JSON 저장/로드
- **`src/lastofus/reports/render.py`**: 자기완결형 HTML 대시보드 생성기
- **`scripts/run_backtest.py`**: CLI (`--fetch`, `--tickers`, `--periods`)
- **`scripts/generate_dashboard.py`**: JSON → HTML 변환 CLI
- **`scripts/daily_orders.py`**: 오늘 걸어야 할 LOC 주문 목록 출력
- **`scripts/publish.sh`**: 웹서버 배포 스크립트
- **`Makefile`**: install / fetch / backtest / dashboard / daily / orders / publish / clean
- **`daily_action.md`**: 매일 해야 할 운용 가이드 (미국/한국 타이밍, cron 설정)
- **`pyproject.toml`**: 의존성 정의 (pandas, numpy, yfinance, plotly, jinja2 등)

### 21:54 — pyarrow 의존성 추가 및 첫 백테스트 실행
- `pyproject.toml`에 `pyarrow>=14.0` 추가 (parquet 지원)
- `uv sync` 로 환경 업데이트
- 전체 백테스트 첫 실행: **9종목 × 6구간 = 54개 조합 완료** (20.1초)
  - TQQQ 최근 3년: CAGR +18.0%, MDD -23.6%, 23사이클
  - TQQQ 2022 하락장: CAGR -44.2%, MDD -49.1%
- `reports/html/index.html` 첫 생성 (4.8 MB)

### 22:03 — nginx 배포 설정 및 서비스 오픈
- 서버 환경 파악: 이 PC(`ideapad-700-15ISK`) = 웹서버 (nginx)
- nginx 설정 확인: `/etc/nginx/conf.d/candle.conf`
  - `stock_candle/` → `/home/cheoljoo/code/candle/dashboard_site/` alias 방식 확인
- `nginx_candle_new.conf` 생성: `infinite_buying/` 블록 추가
- `scripts/setup_nginx.py` 작성 (자동 설정 추가 스크립트)
- sudo 비밀번호 확인 후 nginx 설정 적용 및 재로드
- **서비스 오픈**: http://psncs.iptime.org/infinite_buying/index.html ✅
- 기존 http://psncs.iptime.org/stock_candle/index.html 영향 없음 확인 ✅

### 22:09 — favicon 추가
- `src/lastofus/reports/render.py` HTML 템플릿에 SVG favicon 인라인 삽입
- 디자인: 어두운 네이비 배경(#1a1d2e) + 파란색 **∞** 기호 — "무한매수법" 상징
- `rel="icon"` + `rel="shortcut icon"` 두 가지 모두 등록 (크로스브라우저)
- 외부 파일 없이 `data:` URI로 완전 자기완결형

### 22:12 — 테이블 다크 테마 통일
- Bootstrap 5 기본 흰색 테이블 배경을 다크 테마로 통일
- CSS 변수 방식으로 전환: `--bs-table-bg: #1a1d2e` 등 Bootstrap CSS 변수 완전 덮어쓰기
- `group-header` 행, `table-sm`, `<code>` 블록도 다크 테마 적용
- 충돌 규칙(`background-color: inherit !important`) 제거

### 22:15 — 차트 설명 및 종목명 개선
- 차트 카드 헤더 개편
  - 종목 코드(파란색) + 종목 전체명 + 레버리지 배수 + 국가 국기 표시
  - 구간 배지 표시
  - "위 표에서 종목을 클릭하면 그래프가 바뀝니다" 안내 문구 추가
- 차트 바로 위에 범례 설명 패널 추가
  - 초록 실선: 전략 V2.2 설명
  - 파랑 점선: Buy & Hold 설명
  - 주황 대시: DCA (적립식) 설명 + "원금=100 기준 정규화" 주석
- Plotly 차트 내 title에 종목명·구간 텍스트 직접 표시

### 22:25 — "올해" 구간 추가 (7번째 구간)
- `src/lastofus/config.py`에 `this_year` 구간 추가
  - `{올해}-01-01` ~ 오늘 (실행 시점 `date.today().year` 동적 계산)
  - 내년 실행 시 자동으로 "2027년 (올해)"로 변경
- `get_period_labels()` 함수 신설 (동적 연도 반영)
- 전체 백테스트 재실행: **9종목 × 7구간 = 63개 조합** (20.2초)
  - 2026년 주목 결과: 코스닥150레버리지 +30.9%, KODEX코스닥150 +31.5%, KODEX200 +24.3%
- 대시보드 탭 맨 앞에 "2026년 (올해)" 탭 추가

### 22:30 — Git 관리 파일 정리
- `.gitignore`에 프로젝트 전용 규칙 추가
  - `data/cache/*.parquet` (재다운로드 가능, 수십 MB)
  - `reports/html/index.html` (자동 생성, 4.8 MB)
  - `reports/data/results.json` (자동 생성)
  - `state/*.json` (개인 투자 상태, 민감 데이터)
- Git 저장 대상 / 제외 대상 분류 정리

### 22:34 — 커밋 메시지 작성
- `msg.md` 작성: 커밋 제목, 본문, 변경 파일 요약, 커밋 명령어 포함

### 22:36 — works.md 작성 (이 파일)
- 전체 작업 이력을 시간순으로 정리하여 `works.md` 생성

### 22:44 — 홈 인덱스 페이지 추가
- `http://psncs.iptime.org/` 루트에서 nginx 기본 페이지가 뜨는 문제 해결
- `/home/cheoljoo/code/home/index.html` 생성
  - 다크 테마 (무한매수법 대시보드와 동일 색상 체계 `#0d0f1a` / `#1a1d2e`)
  - Bootstrap 5 카드 그리드 레이아웃
  - 3개 서비스 카드: 🕯️ Stock Candle / ∞ 무한매수법 / 📰 News Arcade
  - 호버 시 카드 상승 애니메이션 + 파란 테두리 강조
  - 인라인 SVG favicon ("P" 심볼)
- nginx `candle.conf`에 `location /` 블록 추가 (`root` 방식)
  - `location = /` (완전 일치)는 index 내부 리다이렉트와 충돌 → `location /` 사용
  - 기존 `/stock_candle/`, `/infinite_buying/`, `/news/` prefix는 더 구체적이므로 우선 처리됨
- 전체 4개 URL 200 응답 확인 ✅

### 2026-06-12 — GitHub 링크 추가 (대시보드 footer)
- `src/lastofus/reports/render.py` footer에 두 링크 추가
  - 📖 [전략 설계 문서 (plan-opus.md)](https://github.com/cheoljoo/the-last-of-us-stock/blob/main/plan-opus.md)
  - 📦 [소스코드 (GitHub)](https://github.com/cheoljoo/the-last-of-us-stock)
- 대시보드 재생성 (5.0 MB)

### 2026-06-13 — plan-opus-v2.md 작성 (추가 실험 계획)
- `additional_info.md` 분석 (VR 심층 분석, V3.0 명세, LOC 가이드, 126~180주차 성과 보고서)
- `plan-opus-v2.md` 작성: 현재 V2.2 구현 위에 추가할 실험 계획 10개 섹션
  - 1-A. 무한매수법 V3.0: 20분할, 별%(15−1.5T)% 공식, TQQQ +15%/SOXL +20%, 쿼터모드
  - 1-B. 밸류리밸런싱(VR): V값·기울기(G)·밴드·풀 관리, 2주 사이클
  - 1-C. 부분복리: 수익 50% 재투자, 손실 시 원금 유지 (비대칭 복리)
  - 1-D. 영혼법: 극한 하락장 대응 (기존 계좌 동결 + 신 시드 병행)
  - 1-E. SOXL 종목 추가
  - 2. 파라미터 그리드: splits × profit_target × reinvest_ratio × star_formula (최대 180조합)
  - 3. VR + 무한매수법 복합 포트폴리오 시뮬레이션
  - 4. 인출식 VR 시뮬레이션 (월 $5,000 인출 20년)
  - 5. 대시보드 확장 계획 (전략 탭, VR 차트, 별% 시각화, 히트맵)
  - 6. Phase 1~5 구현 로드맵

---

## 작업 예정 (TODO)

- [ ] 테스트 코드 작성 (`tests/` 디렉터리)
- [ ] V1 / V2 전략 구현 추가 (버전 비교 기능)
- [ ] 파라미터 그리드 탐색 (분할수, 익절% 조합)
- [ ] 밸류리밸런싱(VR) 전략 구현
- [ ] cron 자동 업데이트 등록
- [ ] `make orders` 결과로 state 파일 대화형 업데이트 기능
