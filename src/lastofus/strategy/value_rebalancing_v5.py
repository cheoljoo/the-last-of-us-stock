"""밸류리밸런싱 VR 5.0 — 오피셜 공식 구현.

출처: https://quantstack.app/vr/overview/ (핵심 용어 & 공식),
      https://quantstack.app/vr/procedure/ (운용 절차)
(quantstack.app 비공식 정리 사이트. 원 방법론 저작권자: 라오어 —
네이버 카페 "무한매수법 & 밸류리밸런싱 공부모임". VR 1~4는 저자가 삭제하고
현재 5.0 단일 버전만 공식이며, 운용 유형(적립식/거치식/인출식)만 다르다.)

핵심 공식:
  다음 V = 현재 V + Pool/G + 적립금(적립식, +) 또는 − 인출금(인출식, −)
  (거치식은 적립금 0)
  밴드 상단 = V × 1.15, 밴드 하단 = V × 0.85  (±15% 오피셜)
  평가금 > 상단 → 평가금이 V로 돌아올 만큼 매도 (받은 현금은 Pool에 편입)
  평가금 < 하단 → 평가금이 V에 도달할 만큼 매수 (단, Pool 사용 한도 내)
  밴드 안 → 거래 없음

유형별 Pool 사용 한도 (한 사이클당 매수에 쓸 수 있는 Pool 비율 상한):
  적립식 75% / 거치식 50% / 인출식 25%
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
    """Run VR 5.0 over *df*.

    Parameters
    ----------
    mode         : "installment"(적립식) | "lumpsum"(거치식) | "withdrawal"(인출식)
    cycle_amount : 사이클당 적립금(installment) 또는 인출 희망액(withdrawal). lumpsum은 무시.

    Returns
    -------
    (rebalances, equity_list, v_curve, total_invested)
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
