"""밸류리밸런싱(VR) — 2주 사이클, V목표값 기반 리밸런싱 전략.

개요:
  V목표(V_target)를 설정하고, 주가가 밴드(±band_pct)를 벗어날 때
  매수/매도로 주식 평가금을 V목표에 맞게 재조정합니다.
  수익 실현분은 현금 풀(Pool)에 쌓이고, 하락 시 풀로 주식을 삽니다.

V목표 성장 공식 (단순화 버전):
  V(n) = V(n-1) × (1 + slope × 0.001)
  예) slope=11 → 사이클마다 1.1% 성장 ≈ 연 33%

참고: 실제 라오어 VR 공식은 미공개. 본 구현은 밴드 리밸런싱 로직을
      검증하기 위한 합리적 근사치입니다.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# V목표 업데이트
# ---------------------------------------------------------------------------

def update_v_target(prev_v: float, slope: int) -> float:
    """V목표를 사이클마다 slope × 0.1% 성장시킵니다."""
    return prev_v * (1.0 + slope * 0.001)


# ---------------------------------------------------------------------------
# Main VR strategy
# ---------------------------------------------------------------------------

def run_vr(
    df: pd.DataFrame,
    principal: float,
    slope: int = 11,
    band_pct: float = 0.08,
    deposit_per_cycle: float = 200.0,
    cycle_days: int = 10,
    equity_frac: float = 0.75,
) -> tuple[list[dict[str, Any]], list[float], list[float], float]:
    """Run 밸류리밸런싱 over *df* (2주 고정 사이클 적립).

    Parameters
    ----------
    df               : OHLCV DataFrame
    principal        : 초기 투자 원금
    slope            : V목표 성장 속도 G (10~13)
    band_pct         : V목표 기준 상하 밴드 비율 (default 8%)
    deposit_per_cycle: 매 사이클마다 풀에 추가하는 현금
    cycle_days       : 1사이클 = N 거래일 (default 10 = 2주)
    equity_frac      : 초기 주식 비중 (default 0.75 = 75%)

    Returns
    -------
    (rebalances, equity_list, v_curve, total_invested)
    """
    if df.empty:
        return [], [], [], principal

    pool_start = principal * (1.0 - equity_frac)
    equity_start = principal * equity_frac

    first_close = float(df["Close"].iloc[0])
    if first_close <= 0:
        return [], [], [], principal

    shares: float = equity_start / first_close
    pool: float = pool_start
    v_target: float = equity_start

    rebalances: list[dict[str, Any]] = []
    equity_list: list[float] = []
    v_curve: list[float] = []
    total_invested: float = principal
    day_in_cycle: int = 0

    for dt, row in df.iterrows():
        close_p: float = float(row["Close"])
        if pd.isna(close_p) or close_p <= 0:
            equity_list.append(shares * 0 + pool)
            v_curve.append(v_target)
            continue

        date_str = str(dt.date()) if hasattr(dt, "date") else str(dt)
        day_in_cycle += 1

        if day_in_cycle >= cycle_days:
            day_in_cycle = 0
            if deposit_per_cycle != 0:
                pool += deposit_per_cycle
                total_invested += max(0.0, deposit_per_cycle)
            v_target = update_v_target(v_target, slope)

            stock_equity = shares * close_p
            band_upper = v_target * (1.0 + band_pct)
            band_lower = v_target * (1.0 - band_pct)

            if stock_equity > band_upper:
                excess = stock_equity - v_target
                sell_qty = min(excess / close_p, shares)
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
                buy_amount = min(shortfall, pool)
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


def run_vr_multi_asset(
    dfs: dict,
    weights: dict,
    principal: float,
    slope: int = 11,
    band_pct: float = 0.08,
    deposit_per_cycle: float = 200.0,
    cycle_days: int = 10,
    equity_frac: float = 0.75,
) -> tuple:
    """VR strategy on a multi-asset portfolio (e.g. QQQ 50% + GLD 50%).

    Parameters
    ----------
    dfs      : {ticker: OHLCV DataFrame}
    weights  : {ticker: fraction}  — must sum to 1.0
    principal: 초기 투자 원금

    Returns
    -------
    (rebalances, equity_list, v_curve, total_invested, dates)
    dates is a list[str] of the common trading dates used.
    """
    if not dfs:
        return [], [], [], principal, []

    # Common trading dates (intersection of all assets)
    common_idx = None
    for df in dfs.values():
        common_idx = df.index if common_idx is None else common_idx.intersection(df.index)

    if common_idx is None or len(common_idx) == 0:
        return [], [], [], principal, []

    aligned = {t: dfs[t].loc[common_idx] for t in dfs}

    # Initialise: 75% equity split by weights, 25% pool
    pool_start = principal * (1.0 - equity_frac)
    equity_start = principal * equity_frac

    first_prices = {t: float(aligned[t]["Close"].iloc[0]) for t in aligned}
    shares: dict[str, float] = {
        t: (equity_start * weights[t]) / first_prices[t] for t in aligned
    }
    pool: float = pool_start
    v_target: float = equity_start
    total_invested: float = principal
    day_in_cycle: int = 0

    rebalances: list[dict] = []
    equity_list: list[float] = []
    v_curve: list[float] = []

    for dt in common_idx:
        prices = {t: float(aligned[t].loc[dt, "Close"]) for t in aligned}
        if any(pd.isna(p) or p <= 0 for p in prices.values()):
            stock_val = sum(shares[t] * prices.get(t, 0) for t in shares)
            equity_list.append(stock_val + pool)
            v_curve.append(v_target)
            continue

        date_str = str(dt.date()) if hasattr(dt, "date") else str(dt)
        day_in_cycle += 1

        if day_in_cycle >= cycle_days:
            day_in_cycle = 0
            if deposit_per_cycle != 0:
                pool += deposit_per_cycle
                total_invested += max(0.0, deposit_per_cycle)
            v_target = update_v_target(v_target, slope)

            stock_equity = sum(shares[t] * prices[t] for t in shares)
            band_upper = v_target * (1.0 + band_pct)
            band_lower = v_target * (1.0 - band_pct)

            if stock_equity > band_upper:
                excess = stock_equity - v_target
                # Sell excess proportionally from each asset
                for t in shares:
                    frac = (shares[t] * prices[t]) / stock_equity
                    sell_qty = (excess * frac) / prices[t]
                    sell_qty = min(sell_qty, shares[t])
                    shares[t] -= sell_qty
                    pool += sell_qty * prices[t]
                rebalances.append({"date": date_str, "type": "SELL_EXCESS",
                                   "stock_equity": stock_equity, "v_target": v_target})

            elif stock_equity < band_lower:
                shortfall = v_target - stock_equity
                buy_amount = min(shortfall, pool)
                if buy_amount > 0:
                    for t in shares:
                        t_buy = buy_amount * weights[t]
                        shares[t] += t_buy / prices[t]
                        pool -= t_buy
                    rebalances.append({"date": date_str, "type": "BUY_SHORTFALL",
                                       "stock_equity": stock_equity, "v_target": v_target})

            # Internal rebalance: restore target weights within equity portion
            new_stock_total = sum(shares[t] * prices[t] for t in shares)
            if new_stock_total > 0:
                for t in shares:
                    target_equity = new_stock_total * weights[t]
                    shares[t] = target_equity / prices[t]

        total_val = sum(shares[t] * prices[t] for t in shares) + pool
        equity_list.append(total_val)
        v_curve.append(v_target)

    dates_str = [
        str(dt.date()) if hasattr(dt, "date") else str(dt) for dt in common_idx
    ]
    return rebalances, equity_list, v_curve, total_invested, dates_str


def run_vr_monthly(
    df: pd.DataFrame,
    principal: float,
    slope: int = 11,
    band_pct: float = 0.08,
    cycle_days: int = 10,
    equity_frac: float = 0.75,
) -> tuple[list[dict[str, Any]], list[float], list[float], float]:
    """VR + 매월 적립 (적립식 VR).

    동일 원금(principal)을 월 수로 나눠 매월 첫 거래일에 풀에 입금.
    2주(cycle_days) 마다 V목표 업데이트 + 밴드 리밸런싱.
    BaH / Monthly DCA와 동일 총 투입금으로 공정 비교.

    Returns
    -------
    (rebalances, equity_list, v_curve, total_invested)
    """
    if df.empty:
        return [], [], [], 0.0

    # 월별 첫 거래일 → 월 적립 스케줄
    first_of_months: set = set()
    seen_ym: set = set()
    for dt in df.index:
        ym = (dt.year, dt.month)
        if ym not in seen_ym:
            seen_ym.add(ym)
            first_of_months.add(dt)

    n_months = len(first_of_months)
    if n_months == 0:
        return [], [], [], 0.0

    monthly_deposit = principal / n_months

    # 첫 달은 주식+풀로 분리 (equity_frac 비율)
    first_deposit = monthly_deposit
    pool: float = first_deposit * (1.0 - equity_frac)
    equity_start = first_deposit * equity_frac

    first_close = float(df["Close"].iloc[0])
    if first_close <= 0:
        return [], [], [], 0.0

    shares: float = equity_start / first_close
    v_target: float = equity_start
    total_invested: float = 0.0
    first_month_done = False

    rebalances: list[dict[str, Any]] = []
    equity_list: list[float] = []
    v_curve: list[float] = []
    day_in_cycle: int = 0

    for dt, row in df.iterrows():
        close_p: float = float(row["Close"])
        if pd.isna(close_p) or close_p <= 0:
            equity_list.append(shares * 0 + pool)
            v_curve.append(v_target)
            continue

        date_str = str(dt.date()) if hasattr(dt, "date") else str(dt)

        # 월 적립금 투입
        if dt in first_of_months:
            if not first_month_done:
                # 첫 달: 이미 초기화됨
                first_month_done = True
                total_invested += first_deposit
            else:
                pool += monthly_deposit
                total_invested += monthly_deposit

        day_in_cycle += 1

        # 2주마다 V목표 업데이트 + 리밸런싱
        if day_in_cycle >= cycle_days:
            day_in_cycle = 0
            v_target = update_v_target(v_target, slope)

            stock_equity = shares * close_p
            band_upper = v_target * (1.0 + band_pct)
            band_lower = v_target * (1.0 - band_pct)

            if stock_equity > band_upper:
                excess = stock_equity - v_target
                sell_qty = min(excess / close_p, shares)
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
                buy_amount = min(shortfall, pool)
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
