feat: 라오어 무한매수법 V2.2 백테스트 시스템 및 웹 대시보드 구현

라오어 무한매수법 V2.2를 기반으로 한 백테스트 엔진과
인터랙티브 웹 대시보드를 구현합니다.

[전략 엔진]
- V2.2 규칙 구현: 40분할 원금, 전반전/후반전 이중 LOC 매수,
  평단가 기준 익절, 40회 소진 시 25% 쿼터컷
- 벤치마크 비교: Buy & Hold, DCA (적립식 40회 균등 분할)
- 계좌 상태 관리: 평단가, 보유수량, 사이클, 쿼터컷 횟수 추적

[백테스트 유니버스]
- 미국: TQQQ, SPXL, UPRO (3x 레버리지), QQQ, VOO (1x 벤치마크)
- 한국: KODEX 레버리지 (122630.KS), KODEX 코스닥150 레버리지 (233740.KS),
        KODEX 200 (069500.KS), KODEX 코스닥150 (229200.KS)
- 구간: 2026년(올해), 최근 3년, 최근 5년, 2022 하락장,
        2020 코로나, 2013-2019 강세장, 전체 구간 (총 7구간)
- 결과: 9종목 × 7구간 = 63개 조합

[지표]
- CAGR, MDD, Sharpe, Sortino, 사이클 수, 쿼터컷 횟수

[웹 대시보드]
- Bootstrap 5 + Plotly.js 기반 단일 자기완결형 HTML
- 다크 테마, 탭 기반 구간 전환, 종목 클릭 시 자본금 곡선 표시
- 전략/Buy&Hold/DCA 3선 비교, 종목명·레버리지·국가 표시
- nginx alias로 http://psncs.iptime.org/infinite_buying/ 서비스
- 기존 stock_candle 페이지 영향 없음

[자동화]
- make daily: 데이터 갱신 → 백테스트 → 대시보드 재생성
- make orders: 오늘 걸어야 할 LOC 매수/매도 주문 출력
- cron 평일 오전 6시 자동 업데이트 권장

[기타]
- .gitignore: parquet 캐시, 생성 HTML/JSON, 개인 state 파일 제외
- nginx 설정 파일 포함 (복구/이전 대비)
- uv 기반 환경 관리 (uv.lock 포함)

---

## 변경 파일 요약

| 분류 | 파일 |
|---|---|
| 전략/엔진 | `src/lastofus/strategy/infinite_v22.py`, `src/lastofus/core/account.py`, `src/lastofus/backtest/engine.py`, `src/lastofus/backtest/metrics.py`, `src/lastofus/backtest/report.py` |
| 데이터 | `src/lastofus/data/loader.py` |
| 대시보드 | `src/lastofus/reports/render.py` |
| 설정 | `src/lastofus/config.py`, `pyproject.toml`, `uv.lock` |
| 스크립트 | `scripts/run_backtest.py`, `scripts/generate_dashboard.py`, `scripts/daily_orders.py`, `scripts/publish.sh`, `scripts/setup_nginx.py` |
| 운영 | `Makefile`, `daily_action.md`, `plan-opus.md`, `nginx_candle_new.conf`, `nginx_infinite_buying.conf` |
| 기타 | `.gitignore` |

---

## 커밋 명령어 (참고용)

```bash
git add .gitignore Makefile daily_action.md nginx_candle_new.conf nginx_infinite_buying.conf \
        plan-opus.md pyproject.toml uv.lock \
        scripts/ src/
git commit -m "feat: 라오어 무한매수법 V2.2 백테스트 시스템 및 웹 대시보드 구현"
```

> `data/`, `reports/`, `state/` 는 .gitignore 에 의해 자동 제외됩니다.
