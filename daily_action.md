# 라오어 무한매수법 V2.2 — 매일 할 일 가이드

## 개요

이 문서는 라오어 무한매수법 V2.2를 실제로 운용할 때 **매일 해야 하는 작업**을 설명합니다.

---

## US 주식 (미국 ETF: TQQQ, SPXL, UPRO, QQQ, VOO)

### 타이밍
- **미국 동부 시간** 오후 3:50~4:00 (장 마감 직전)
- **한국 시간** 기준: 여름(EDT) 오전 4:50~5:00 / 겨울(EST) 오전 5:50~6:00

### 절차
1. 터미널에서 오늘의 주문 목록 확인:
   ```bash
   make orders
   # 또는
   uv run python scripts/daily_orders.py --tickers TQQQ SPXL UPRO QQQ VOO
   ```

2. 출력 내용을 보고 **LOC(Limit On Close)** 매수 주문 입력:
   - 목표가 도달 시 → **지정가 매도** 주문
   - 쿼터컷 필요 시 → **장 마감 시장가 매도** 주문
   - 매수 필요 시 → **LOC 지정가 매수** 주문

3. 체결 확인 후 상태 파일 업데이트:
   ```bash
   uv run python scripts/daily_orders.py --update
   ```
   또는 직접 `state/TICKER_state.json` 파일을 수정합니다.

---

## 한국 주식 (KR ETF: KODEX레버리지, KODEX코스닥150레버리지 등)

### 타이밍
- **한국 시간** 오후 3:00~3:20 (장 마감 전 20~30분)

### 절차
1. 터미널에서 오늘의 주문 목록 확인:
   ```bash
   make orders
   # 또는
   uv run python scripts/daily_orders.py --tickers 122630.KS 233740.KS 069500.KS 229200.KS
   ```

2. HTS/MTS에서 주문 입력:
   - 목표가 도달 시 → **지정가 매도** (평균단가 × 1.07)
   - 쿼터컷 필요 시 → **시장가 매도** (보유수량 25%)
   - 매수 필요 시 → **LOC 지정가 매수** 또는 **시장가 매수**

3. 체결 후 state 파일 업데이트:
   ```bash
   uv run python scripts/daily_orders.py --update
   ```

---

## 백테스트 및 대시보드 업데이트

### 전체 업데이트 (매일 1회 권장)
```bash
make daily
```
이 명령은 다음을 순서대로 실행합니다:
1. `make fetch` — 최신 시세 데이터 다운로드
2. `make backtest` — 백테스트 실행 및 결과 저장
3. `make dashboard` — HTML 대시보드 생성

### 개별 실행
```bash
make fetch       # 데이터만 다운로드
make backtest    # 백테스트만 실행
make dashboard   # 대시보드만 생성
```

### 특정 티커/기간만 테스트
```bash
uv run python scripts/run_backtest.py --tickers TQQQ SPXL --periods 3yr 5yr
```

---

## 상태 파일 관리

각 티커의 현재 포지션은 `state/` 디렉토리에 JSON으로 저장됩니다.

### 파일 형식 (`state/TQQQ_state.json`)
```json
{
    "ticker": "TQQQ",
    "shares": 12.5,
    "avg_price": 45.23,
    "rounds_done": 8.0,
    "cycle_count": 3,
    "quarter_cut_count": 1,
    "cash": 7500.0,
    "principal": 10000.0,
    "splits": 40
}
```

### 수동 초기화 (새 사이클 시작)
파일을 삭제하거나 `shares`, `avg_price`, `rounds_done`을 0으로 초기화합니다.

---

## 권장 크론 스케줄 (자동화)

```cron
# 평일 오전 6시 KST — 미국 장 마감 후 데이터 업데이트 (EDT 기준 오후 5시)
0 6 * * 1-5  cd /home/cheoljoo/code/the-last-of-us-stock && make daily >> /tmp/infinite_buy.log 2>&1

# 평일 오후 3시 30분 KST — 한국 장 마감 후 업데이트
30 15 * * 1-5  cd /home/cheoljoo/code/the-last-of-us-stock && make daily >> /tmp/infinite_buy.log 2>&1
```

크론에 추가하는 방법:
```bash
crontab -e
```

---

## 대시보드 URL

- **로컬**: `file:///home/cheoljoo/code/the-last-of-us-stock/reports/html/index.html`
- **배포 후**: http://psncs.iptime.org/infinite_buying/index.html
- **기존 대시보드**: http://psncs.iptime.org/stock_candle/index.html

서버 배포:
```bash
make publish
# 또는 서버/디렉토리를 지정하려면
PUBLISH_SERVER=user@myserver.com PUBLISH_DIR=/var/www/html/infinite_buying/ make publish
```

---

## 전략 핵심 요약

| 구분 | 조건 | 동작 |
|------|------|------|
| 매도 (이익 실현) | 당일 고가 ≥ 평단가 × (1 + 목표수익률) | 전량 지정가 매도 |
| 쿼터컷 | rounds_done ≥ 40 | 보유수량 25% 시장가 매도 |
| 신규 매수 | shares == 0 | 1유닛 시장가 매수 |
| 전반전 LOC1 | 전반전 (≤50%), 종가 ≤ 평단가 | 0.5유닛 LOC 매수 |
| 전반전 LOC2 | 전반전 (≤50%), 종가 ≤ 평단가×1.05 | 0.5유닛 LOC 매수 |
| 후반전 매수 | 후반전 (>50%), 종가 ≤ 평단가 | 1유닛 LOC 매수 |

---

## 위험 경고

> **이 시스템은 교육 및 연구 목적으로 제작되었습니다.**
>
> - 레버리지 ETF는 일반 ETF보다 훨씬 높은 위험을 수반합니다.
> - 장기 하락장에서는 원금 손실이 매우 클 수 있습니다.
> - 백테스트 결과는 과거 데이터에 기반하며 미래 수익을 보장하지 않습니다.
> - 모든 투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.
> - 여유 자금으로만 투자하십시오.
