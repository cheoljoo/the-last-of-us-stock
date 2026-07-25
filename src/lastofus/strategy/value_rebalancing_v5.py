"""밸류리밸런싱 VR 5.0 — 오피셜 공식 구현.

References
----------
- https://quantstack.app/vr/          ("밸류리밸런싱 VR 5.0 개요", 문서 구성/핵심 공식 요약/
  유형별 파라미터 비교/공통 원칙. ※ 사이트 상 실제 슬러그는 `/vr/`이며 `/vr/overview/`가 아님 —
  `/vr/overview/`는 아래 "핵심 용어 & 공식" 문서를 가리킨다.)
- https://quantstack.app/vr/overview/  ("VR 5.0 핵심 용어 & 공식", 발표일 2022-04-15,
  원글 posts/009, cafe.naver.com/infinitebuying/38944)
- https://quantstack.app/vr/procedure/ ("VR 5.0 운용 절차 (2주 사이클)")
- https://quantstack.app/vr/installment/, /vr/lumpsum/, /vr/withdrawal/, /vr/convert/
  (적립식/거치식/인출식 유형별 문서 및 유형 전환 가이드 — 공식·매매 로직은 세 유형 모두 동일하고
  Pool 사용 한도·권장 G값만 다르다)

quantstack.app은 라오어(네이버 카페 "무한매수법 & 밸류리밸런싱 공부모임")가 공개한 방법론을
정리하는 비공식 3자 사이트다. VR 1~4는 원저작자가 혼란 방지를 위해 이미 삭제했고 현재는
**5.0 단일 버전**만 존재하며, 적립식/거치식/인출식은 그 위의 운용 "유형" 차이일 뿐이다.

핵심 개념 (4가지 용어, /vr/overview/ "4가지 용어" 절)
------------------------------------------------------
  V (Value)   : 레버리지 ETF 평가금의 기준선. 상승률 공식으로 2주(cycle_days)마다 갱신.
  P (Pool)    : 보유 현금.
  밴드         : V × (1−band_pct) ~ V × (1+band_pct). 오피셜 값은 ±15%.
  G (Gradient): V 기울기를 결정하는 분모. 클수록 V 성장이 느려져 안정적
                (G=10→연 수익배율 2.98x, G=20→2.74x, G=40→2.38x, /vr/overview/ "G 값 가이드" 표 기준).

상승률(다음 V) 공식 — /vr/overview/ "상승률 공식 (기본)", /vr/procedure/ "(1) 새 V 계산"
--------------------------------------------------------------------------------------
    다음 V = 현재 V + Pool/G + 적립금(적립식, +금액) 또는 − 인출금(인출식, −금액)
    (거치식은 적립금/인출금 항이 0)

2주 사이클 매수/매도 판단 — /vr/procedure/ "2. 매수 / 매도 판단"
------------------------------------------------------------------
    밴드 상단(V×1.15) 초과 → 평가금이 V로 돌아올 만큼 매도, 받은 현금은 Pool에 편입
    밴드 하단(V×0.85) 미만 → 평가금이 V에 도달할 만큼 매수, 단 Pool 사용 한도 내에서만
    밴드 안(0.85V~1.15V)   → 매수도 매도도 없음

유형별 Pool 사용 한도·권장 G값 (/vr/overview/ "Pool 사용 제한 (유형별)", /vr/ "유형별 파라미터 비교")
------------------------------------------------------------------------------------------------
    적립식: 한 사이클당 매수에 (적립 후) Pool의 75%까지, 권장 시작 G=/10
    거치식: 한 사이클당 매수에 Pool의 50%까지,                권장 시작 G=/10
    인출식: 한 사이클당 매수에 (인출 후) Pool의 25%까지,        권장 시작 G=/20
    (1년 단위로 G를 /11→/12→/13… 점진적으로 완화하는 것을 라오어님이 권장하나,
     본 구현은 백테스트 전체 기간에 고정 G를 사용하는 단순화 버전이다)
"""
from __future__ import annotations

from typing import Any

import pandas as pd

POOL_LIMIT = {"installment": 0.75, "lumpsum": 0.50, "withdrawal": 0.25}


def run_vr5(
    df: pd.DataFrame,
    principal: float,
    g: int = 10,
    band_pct: float = 0.15,
    mode: str = "installment",
    cycle_amount: float = 200.0,
    cycle_days: int = 10,
    equity_frac: float = 0.75,
) -> tuple[list[dict[str, Any]], list[float], list[float], float]:
    """Run VR 5.0 over *df* — 2주(cycle_days) 고정 사이클로 V 갱신 + 밴드 리밸런싱.

    시작 시 principal을 equity_frac : (1−equity_frac) 비율로 주식/Pool에 배분하고
    (초기 V = 초기 주식 평가금), cycle_days 거래일마다:
      1. 다음 V = V + Pool/g + 적립금(or −인출금) 계산 (모드에 따라 부호/유무가 다름)
      2. 밴드(V×(1±band_pct)) 재설정
      3. 평가금이 상단 초과 → 초과분만큼 매도 (평가금을 V로 되돌림)
         평가금이 하단 미만 → 부족분만큼 매수하되 Pool×pool_limit(모드별) 한도 내에서만

    Parameters
    ----------
    df           : OHLCV DataFrame (Close 컬럼 사용)
    principal    : 초기 투자 원금 (주식+Pool 합계)
    g            : Gradient. V 성장 속도를 늦추는 분모 (권장: 적립식/거치식 10, 인출식 20)
    band_pct     : 밴드 폭 (오피셜 0.15 = ±15%)
    mode         : "installment"(적립식) | "lumpsum"(거치식) | "withdrawal"(인출식).
                   Pool 사용 한도(POOL_LIMIT)가 모드별로 다르게 적용된다.
    cycle_amount : 사이클당 적립금(installment, +) 또는 인출 희망액(withdrawal, Pool 내에서만
                   가능한 만큼 인출). lumpsum 모드에서는 무시된다.
    cycle_days   : 1사이클 거래일 수 (2주 ≈ 10거래일)
    equity_frac  : 시작 시 주식 비중 (오피셜 예시 75%, 나머지 25%는 Pool)

    Returns
    -------
    rebalances     : 사이클마다 발생한 매수/매도 이벤트 리스트
                      (type: "SELL_EXCESS" | "BUY_SHORTFALL")
    equity_list    : df와 같은 길이의 일별 총평가금(주식+Pool) 리스트
    v_curve        : 일별 V목표값 리스트 (사이클 사이는 직전 값 유지)
    total_invested : 누적 투입 원금 (installment는 principal+적립 누계, 그 외는 principal)
    """
    if df.empty:
        return [], [], [], principal

    first_close = float(df["Close"].iloc[0])
    if first_close <= 0:
        return [], [], [], principal

    pool_limit = POOL_LIMIT.get(mode, 0.75)

    equity0 = principal * equity_frac
    pool = principal * (1.0 - equity_frac)
    shares = equity0 / first_close
    v_target = equity0

    total_invested = principal

    rebalances: list[dict[str, Any]] = []
    equity_list: list[float] = []
    v_curve: list[float] = []
    day_in_cycle = 0

    for dt, row in df.iterrows():
        close_p = float(row["Close"])
        if pd.isna(close_p) or close_p <= 0:
            equity_list.append(shares * 0 + pool)
            v_curve.append(v_target)
            continue

        date_str = str(dt.date()) if hasattr(dt, "date") else str(dt)
        day_in_cycle += 1

        if day_in_cycle >= cycle_days:
            day_in_cycle = 0

            # (1) 새 V 계산: next V = V + Pool/G + 적립금(또는 −인출금)
            delta = pool / g
            if mode == "installment":
                pool += cycle_amount
                total_invested += cycle_amount
                v_target = v_target + delta + cycle_amount
            elif mode == "withdrawal":
                withdraw = min(cycle_amount, pool)  # Pool 내에서만 인출 가능
                pool -= withdraw
                v_target = v_target + delta - cycle_amount
            else:  # lumpsum
                v_target = v_target + delta

            # (2) 밴드 재설정 + 매수/매도 판단
            band_upper = v_target * (1.0 + band_pct)
            band_lower = v_target * (1.0 - band_pct)
            stock_equity = shares * close_p

            if stock_equity > band_upper:
                sell_amount = stock_equity - v_target
                sell_qty = min(sell_amount / close_p, shares)
                proceeds = sell_qty * close_p
                shares -= sell_qty
                pool += proceeds
                rebalances.append({
                    "date": date_str, "type": "SELL_EXCESS",
                    "price": close_p, "qty": sell_qty,
                    "v_target": v_target, "stock_equity": stock_equity,
                })

            elif stock_equity < band_lower:
                shortfall = v_target - stock_equity
                buy_amount = min(shortfall, pool * pool_limit)
                if buy_amount > 0:
                    buy_qty = buy_amount / close_p
                    shares += buy_qty
                    pool -= buy_amount
                    rebalances.append({
                        "date": date_str, "type": "BUY_SHORTFALL",
                        "price": close_p, "qty": buy_qty,
                        "v_target": v_target, "stock_equity": stock_equity,
                    })

        equity_list.append(shares * close_p + pool)
        v_curve.append(v_target)

    return rebalances, equity_list, v_curve, total_invested
