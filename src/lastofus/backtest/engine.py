"""Backtest engine – orchestrates data loading, strategy runs, and metrics."""
from __future__ import annotations

from typing import Any

import pandas as pd

from lastofus.config import (
    TICKER_CONFIG,
    DEFAULT_PRINCIPAL_USD,
    DEFAULT_PRINCIPAL_KRW,
    get_periods,
)
from lastofus.core.account import Account
from lastofus.data.loader import fetch_ohlcv
from lastofus.strategy.infinite_v22 import run_strategy, run_bah, run_dca
from lastofus.backtest.metrics import compute_metrics

MIN_BARS = 20  # skip a ticker-period combo if fewer bars than this


def run_single(
    ticker: str,
    period_key: str,
    start: str,
    end: str,
    principal: float | None = None,
) -> dict[str, Any] | None:
    """Run strategy + benchmarks for one ticker × one period.

    Returns a result dict, or None if there is insufficient data.
    """
    cfg = TICKER_CONFIG.get(ticker, {})
    if principal is None:
        principal = DEFAULT_PRINCIPAL_KRW if cfg.get("market") == "KR" else DEFAULT_PRINCIPAL_USD

    profit_target: float = cfg.get("profit_target", 0.10)
    splits: int          = cfg.get("splits", 40)

    # Clamp start date to the ticker's first trading day
    ticker_start = cfg.get("start_date", "2000-01-01")
    effective_start = max(start, ticker_start)

    try:
        df = fetch_ohlcv(ticker, effective_start, end)
    except Exception as exc:
        print(f"    WARNING: could not load {ticker} [{period_key}]: {exc}")
        return None

    if df is None or len(df) < MIN_BARS:
        return None

    dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in df.index]

    # ---- Strategy --------------------------------------------------------
    acct = Account(principal=principal, splits=splits)
    trades, equity_strat = run_strategy(df, acct, profit_target)

    # ---- Benchmarks ------------------------------------------------------
    _, equity_bah = run_bah(df, principal)
    _, equity_dca = run_dca(df, principal, splits)

    metrics_strat = compute_metrics(equity_strat, dates)
    metrics_bah   = compute_metrics(equity_bah,   dates)
    metrics_dca   = compute_metrics(equity_dca,   dates)

    return {
        "ticker":          ticker,
        "ticker_name":     cfg.get("name", ticker),
        "market":          cfg.get("market", "US"),
        "leverage":        cfg.get("leverage", 1),
        "period":          period_key,
        "start":           dates[0] if dates else effective_start,
        "end":             dates[-1] if dates else end,
        "n_bars":          len(df),
        "principal":       principal,
        "profit_target":   profit_target,
        "splits":          splits,
        # Metrics dicts
        "metrics_strategy": metrics_strat,
        "metrics_bah":      metrics_bah,
        "metrics_dca":      metrics_dca,
        # Account final state
        "final_cycles":        acct.cycle_count,
        "final_quarter_cuts":  acct.quarter_cut_count,
        "final_equity":        acct.equity(float(df["Close"].iloc[-1])),
        "final_cash":          acct.cash,
        "final_shares":        acct.shares,
        "final_avg_price":     acct.avg_price,
        "final_rounds_done":   acct.rounds_done,
        # Equity curves (thinned to max 1500 points to keep JSON small)
        "dates":           _thin(dates, 1500),
        "equity_strategy": _thin(equity_strat, 1500),
        "equity_bah":      _thin(equity_bah, 1500),
        "equity_dca":      _thin(equity_dca, 1500),
        # Trade log (trimmed to last 200 for brevity)
        "trades":          trades[-200:],
    }


def run_all(
    tickers: list[str] | None = None,
    periods: dict[str, tuple[str, str]] | None = None,
    principal: float | None = None,
) -> dict[str, Any]:
    """Run strategy for every ticker × period combination.

    Returns a nested dict: results[ticker][period] = result_dict.
    """
    if tickers is None:
        tickers = list(TICKER_CONFIG.keys())
    if periods is None:
        periods = get_periods()

    results: dict[str, dict[str, Any]] = {}
    total = len(tickers) * len(periods)
    done = 0

    for ticker in tickers:
        results[ticker] = {}
        cfg = TICKER_CONFIG.get(ticker, {})
        p = principal
        if p is None:
            p = DEFAULT_PRINCIPAL_KRW if cfg.get("market") == "KR" else DEFAULT_PRINCIPAL_USD

        for period_key, (start, end) in periods.items():
            done += 1
            print(f"  [{done}/{total}] {ticker} / {period_key} ...", end=" ", flush=True)
            try:
                res = run_single(ticker, period_key, start, end, p)
                if res is None:
                    print("SKIP (insufficient data)")
                    results[ticker][period_key] = {"skip": True, "reason": "데이터 없음"}
                else:
                    cagr = res["metrics_strategy"]["cagr"]
                    mdd  = res["metrics_strategy"]["mdd"]
                    print(f"OK  CAGR={cagr:.1%}  MDD={mdd:.1%}")
                    results[ticker][period_key] = res
            except Exception as exc:
                print(f"ERROR: {exc}")
                results[ticker][period_key] = {"skip": True, "reason": str(exc)}

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _thin(lst: list, max_points: int) -> list:
    """Down-sample *lst* to at most *max_points* evenly spaced elements."""
    n = len(lst)
    if n <= max_points:
        return lst
    step = n / max_points
    indices = [int(i * step) for i in range(max_points)]
    indices[-1] = n - 1  # always include last point
    return [lst[i] for i in indices]
