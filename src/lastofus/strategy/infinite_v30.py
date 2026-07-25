"""무한매수법 V3.0 strategy implementation.

Key changes from V2.2:
  - 20-split (half of V2.2's 40)
  - Star% formula: (15 − 1.5×T)%  where T = rounds_done (0-based)
  - Higher profit targets: US 3x +15%, SOXL +20%
  - Quarter mode (T >= splits) instead of simple quarter-cut
  - Partial compounding supported via Account.reinvest_ratio
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from lastofus.core.account import Account


# ---------------------------------------------------------------------------
# Star% formula
# ---------------------------------------------------------------------------

def star_pct(rounds_done: float, splits: int = 20) -> float:
    """V3.0 star percent: (15 − 1.5×T)% converging from +15% toward negative.

    At T=0   → +15%  (초기: 평단보다 15% 높은 곳도 매수 시도)
    At T=10  →   0%  (평단 근처)
    At T=19  → −13.5% (평단보다 낮아야만 매수)
    """
    T = min(rounds_done, splits - 1)
    # Scale to always span 15%→−(splits-1)*1.5% over the full split range
    ratio = T / max(splits - 1, 1) * (splits - 1)
    return (15.0 - 1.5 * ratio) / 100.0


# ---------------------------------------------------------------------------
# Main V3.0 strategy
# ---------------------------------------------------------------------------

def run_strategy_v30(
    df: pd.DataFrame,
    account: Account,
    profit_target: float,
) -> tuple[list[dict[str, Any]], list[float]]:
    """Run the V3.0 strategy over *df* using *account*.

    V3.0 differences from V2.2:
    - star% formula drives buy price (not fixed avg×1.05)
    - Quarter mode: sell 1/4 at close when rounds exhausted, halt buying
    - Partial compounding via account.reinvest_ratio
    """
    trades: list[dict[str, Any]] = []
    equity_list: list[float] = []

    splits = account.splits  # should be 20 for authentic V3.0

    for i, (dt, row) in enumerate(df.iterrows()):
        open_p: float  = float(row.get("Open", row["Close"]))
        high_p: float  = float(row["High"])
        low_p: float   = float(row["Low"])
        close_p: float = float(row["Close"])

        if pd.isna(close_p) or close_p <= 0:
            equity_list.append(account.equity(0))
            continue

        date_str = str(dt.date()) if hasattr(dt, "date") else str(dt)

        # ------------------------------------------------------------------
        # Step 1 – SELL CHECK (profit target)
        # ------------------------------------------------------------------
        if account.shares > 0 and account.avg_price > 0:
            sell_limit = account.avg_price * (1.0 + profit_target)
            if high_p >= sell_limit:
                proceeds = account.sell(sell_limit, account.shares)
                trades.append({
                    "date": date_str, "type": "SELL_TARGET",
                    "price": sell_limit, "qty": proceeds / sell_limit,
                    "proceeds": proceeds, "cycle": account.cycle_count,
                })
                account.reset_cycle()  # applies compounding if reinvest_ratio > 0
                equity_list.append(account.equity(close_p))
                continue

        # ------------------------------------------------------------------
        # Step 2 – QUARTER MODE (rounds exhausted)
        # V3.0: sell 1/4 at close (MOC simulation), pause buying
        # ------------------------------------------------------------------
        if account.rounds_done >= splits and account.shares > 0:
            sell_qty = account.shares * 0.25
            freed = account.sell(close_p, sell_qty)
            # Reduce rounds proportionally to freed cash
            rounds_reduction = freed / account.unit_amount
            account.rounds_done = max(0.0, account.rounds_done - rounds_reduction)
            account.quarter_cut_count += 1
            trades.append({
                "date": date_str, "type": "QUARTER_MODE",
                "price": close_p, "qty": sell_qty,
                "proceeds": freed, "cycle": account.cycle_count,
            })
            equity_list.append(account.equity(close_p))
            continue  # no buy today

        # ------------------------------------------------------------------
        # Step 3 – BUY LOGIC
        # ------------------------------------------------------------------
        unit = account.unit_amount
        T = account.rounds_done  # current round index

        # 3a) New cycle – no position: buy 1 unit at close
        if account.shares == 0:
            spent = account.buy(close_p, unit)
            if spent > 0:
                account.rounds_done += 1.0
                trades.append({
                    "date": date_str, "type": "BUY_NEW",
                    "price": close_p, "qty": spent / close_p,
                    "spent": spent, "cycle": account.cycle_count,
                })

        elif T < splits / 2:
            # 3b) 전반전 — dual LOC: star_price (0.5) + avg_price (0.5)
            half = unit / 2.0
            sp = account.avg_price * (1.0 + star_pct(T, splits))

            if close_p <= sp:
                spent = account.buy(close_p, half)
                if spent > 0:
                    account.rounds_done += 0.5
                    trades.append({
                        "date": date_str, "type": "BUY_STAR",
                        "price": close_p, "qty": spent / close_p,
                        "spent": spent, "cycle": account.cycle_count,
                    })

            if close_p <= account.avg_price:
                spent = account.buy(close_p, half)
                if spent > 0:
                    account.rounds_done += 0.5
                    trades.append({
                        "date": date_str, "type": "BUY_AVG",
                        "price": close_p, "qty": spent / close_p,
                        "spent": spent, "cycle": account.cycle_count,
                    })

        else:
            # 3c) 후반전 — single LOC at star_price (may be below avg_price)
            sp = account.avg_price * (1.0 + star_pct(T, splits))
            if close_p <= sp:
                spent = account.buy(close_p, unit)
                if spent > 0:
                    account.rounds_done += 1.0
                    trades.append({
                        "date": date_str, "type": "BUY_STAR_HALF",
                        "price": close_p, "qty": spent / close_p,
                        "spent": spent, "cycle": account.cycle_count,
                    })

        equity_list.append(account.equity(close_p))

    return trades, equity_list


# ---------------------------------------------------------------------------
# Benchmarks (re-export from V2.2 for convenience)
# ---------------------------------------------------------------------------

from lastofus.strategy.infinite_v22 import run_bah, run_dca  # noqa: E402
