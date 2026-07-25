"""라오어 무한매수법 V2.2 strategy implementation.

Entry points:
- run_strategy(df, account, profit_target)  → (trades, equity_series)
- run_bah(df, principal)                    → (trades, equity_series)
- run_dca(df, principal, splits)            → (trades, equity_series)
- run_monthly_dca(df, principal)            → (trades, equity_series, total_invested)
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from lastofus.core.account import Account


# ---------------------------------------------------------------------------
# Main strategy
# ---------------------------------------------------------------------------

def run_strategy(
    df: pd.DataFrame,
    account: Account,
    profit_target: float,
) -> tuple[list[dict[str, Any]], list[float]]:
    """Run the V2.2 strategy over *df* using *account*.

    Returns:
        trades      – list of trade event dicts
        equity_list – portfolio equity at close of each bar (len == len(df))
    """
    trades: list[dict[str, Any]] = []
    equity_list: list[float] = []

    splits = account.splits

    for i, (dt, row) in enumerate(df.iterrows()):
        open_p: float = float(row.get("Open", row["Close"]))
        high_p: float = float(row["High"])
        low_p: float  = float(row["Low"])
        close_p: float = float(row["Close"])

        if pd.isna(close_p) or close_p <= 0:
            equity_list.append(account.equity(close_p if not pd.isna(close_p) else 0))
            continue

        # ------------------------------------------------------------------
        # Step 1 – CHECK SELL (profit target hit intraday)
        # ------------------------------------------------------------------
        if account.shares > 0 and account.avg_price > 0:
            sell_limit = account.avg_price * (1.0 + profit_target)
            if high_p >= sell_limit:
                proceeds = account.sell(sell_limit, account.shares)
                trades.append({
                    "date":  str(dt.date()) if hasattr(dt, "date") else str(dt),
                    "type":  "SELL_TARGET",
                    "price": sell_limit,
                    "qty":   proceeds / sell_limit,
                    "proceeds": proceeds,
                    "cycle": account.cycle_count,
                })
                account.reset_cycle()
                equity_list.append(account.equity(close_p))
                continue  # no buy today

        # ------------------------------------------------------------------
        # Step 2 – CHECK QUARTER CUT (rounds exhausted)
        # ------------------------------------------------------------------
        if account.rounds_done >= splits and account.shares > 0:
            sell_qty = account.shares * 0.25
            freed_cash = account.sell(close_p, sell_qty)
            rounds_reduction = freed_cash / account.unit_amount
            account.rounds_done = max(0.0, account.rounds_done - rounds_reduction)
            account.quarter_cut_count += 1
            trades.append({
                "date":  str(dt.date()) if hasattr(dt, "date") else str(dt),
                "type":  "QUARTER_CUT",
                "price": close_p,
                "qty":   sell_qty,
                "proceeds": freed_cash,
                "cycle": account.cycle_count,
            })
            equity_list.append(account.equity(close_p))
            continue  # no buy today

        # ------------------------------------------------------------------
        # Step 3 – BUY LOGIC
        # ------------------------------------------------------------------
        unit = account.unit_amount

        # 3a) New cycle – no position
        if account.shares == 0:
            spent = account.buy(close_p, unit)
            if spent > 0:
                account.rounds_done += 1.0
                trades.append({
                    "date":  str(dt.date()) if hasattr(dt, "date") else str(dt),
                    "type":  "BUY_NEW",
                    "price": close_p,
                    "qty":   spent / close_p,
                    "spent": spent,
                    "cycle": account.cycle_count,
                })

        elif account.progress <= 0.5:
            # 3b) 전반전 – dual LOC orders
            half = unit / 2.0
            loc1_filled = close_p <= account.avg_price
            loc2_filled = close_p <= account.avg_price * 1.05

            if loc1_filled:
                spent = account.buy(close_p, half)
                if spent > 0:
                    account.rounds_done += 0.5
                    trades.append({
                        "date":  str(dt.date()) if hasattr(dt, "date") else str(dt),
                        "type":  "BUY_LOC1",
                        "price": close_p,
                        "qty":   spent / close_p,
                        "spent": spent,
                        "cycle": account.cycle_count,
                    })

            if loc2_filled:
                spent = account.buy(close_p, half)
                if spent > 0:
                    account.rounds_done += 0.5
                    trades.append({
                        "date":  str(dt.date()) if hasattr(dt, "date") else str(dt),
                        "type":  "BUY_LOC2",
                        "price": close_p,
                        "qty":   spent / close_p,
                        "spent": spent,
                        "cycle": account.cycle_count,
                    })

        else:
            # 3c) 후반전 – single conservative buy
            if close_p <= account.avg_price:
                spent = account.buy(close_p, unit)
                if spent > 0:
                    account.rounds_done += 1.0
                    trades.append({
                        "date":  str(dt.date()) if hasattr(dt, "date") else str(dt),
                        "type":  "BUY_SECOND",
                        "price": close_p,
                        "qty":   spent / close_p,
                        "spent": spent,
                        "cycle": account.cycle_count,
                    })

        equity_list.append(account.equity(close_p))

    return trades, equity_list


# ---------------------------------------------------------------------------
# Buy-and-Hold benchmark
# ---------------------------------------------------------------------------

def run_bah(
    df: pd.DataFrame,
    principal: float,
) -> tuple[list[dict[str, Any]], list[float]]:
    """Buy as many shares as possible at the first close, hold forever."""
    trades: list[dict[str, Any]] = []
    equity_list: list[float] = []

    if df.empty:
        return trades, equity_list

    shares = 0.0
    cash = principal
    invested = False

    for i, (dt, row) in enumerate(df.iterrows()):
        close_p = float(row["Close"])
        if pd.isna(close_p) or close_p <= 0:
            equity_list.append(cash + shares * 0)
            continue

        if not invested:
            shares = cash / close_p
            cost = shares * close_p
            cash -= cost
            invested = True
            trades.append({
                "date":  str(dt.date()) if hasattr(dt, "date") else str(dt),
                "type":  "BAH_BUY",
                "price": close_p,
                "qty":   shares,
                "spent": cost,
            })

        equity_list.append(cash + shares * close_p)

    return trades, equity_list


# ---------------------------------------------------------------------------
# DCA benchmark (기존: 초반 N일 균등 투자)
# ---------------------------------------------------------------------------

def run_dca(
    df: pd.DataFrame,
    principal: float,
    splits: int = 40,
) -> tuple[list[dict[str, Any]], list[float]]:
    """Invest principal/splits on each of the first *splits* trading days."""
    trades: list[dict[str, Any]] = []
    equity_list: list[float] = []

    if df.empty:
        return trades, equity_list

    cash = principal
    shares = 0.0
    unit = principal / splits
    days_invested = 0

    for i, (dt, row) in enumerate(df.iterrows()):
        close_p = float(row["Close"])
        if pd.isna(close_p) or close_p <= 0:
            equity_list.append(cash + shares * 0)
            continue

        if days_invested < splits and cash >= unit * 0.999:
            qty = unit / close_p
            shares += qty
            cash -= unit
            days_invested += 1
            trades.append({
                "date":  str(dt.date()) if hasattr(dt, "date") else str(dt),
                "type":  "DCA_BUY",
                "price": close_p,
                "qty":   qty,
                "spent": unit,
                "day":   days_invested,
            })

        equity_list.append(cash + shares * close_p)

    return trades, equity_list


# ---------------------------------------------------------------------------
# Monthly DCA benchmark (적립식 — 매월 초 균등 투자)
# ---------------------------------------------------------------------------

def run_monthly_dca(
    df: pd.DataFrame,
    principal: float,
) -> tuple[list[dict[str, Any]], list[float], float]:
    """매월 첫 거래일에 균등 금액을 적립 투자.

    전체 원금(principal)을 총 월 수로 나눠 매월 초에 전량 매수.
    BaH / DCA와 동일 총 원금으로 공정 비교.

    Returns
    -------
    (trades, equity_series, total_invested)
    """
    if df.empty:
        return [], [], 0.0

    first_of_months: set = set()
    seen_ym: set = set()
    for dt in df.index:
        ym = (dt.year, dt.month)
        if ym not in seen_ym:
            seen_ym.add(ym)
            first_of_months.add(dt)

    n_months = len(first_of_months)
    if n_months == 0:
        return [], [], 0.0

    monthly = principal / n_months

    shares = 0.0
    cash = 0.0
    total_invested = 0.0
    trades: list[dict[str, Any]] = []
    equity_list: list[float] = []

    for dt, row in df.iterrows():
        close_p = float(row["Close"])
        if pd.isna(close_p) or close_p <= 0:
            equity_list.append(cash + shares * 0)
            continue

        if dt in first_of_months:
            cash += monthly
            total_invested += monthly
            qty = cash / close_p
            shares += qty
            cash = 0.0
            trades.append({
                "date":  str(dt.date()) if hasattr(dt, "date") else str(dt),
                "type":  "MONTHLY_DCA",
                "price": close_p,
                "qty":   qty,
                "spent": monthly,
            })

        equity_list.append(cash + shares * close_p)

    return trades, equity_list, total_invested
