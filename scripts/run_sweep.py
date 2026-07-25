#!/usr/bin/env python
"""파라미터 그리드 탐색 — splits × profit_target × reinvest_ratio 조합 백테스트.

Usage:
    uv run python scripts/run_sweep.py [--tickers TQQQ SOXL] [--period 3yr]
    uv run python scripts/run_sweep.py --tickers TQQQ --period 2022

출력: reports/data/sweep_results.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from lastofus.config import TICKER_CONFIG, DEFAULT_PRINCIPAL_USD, DEFAULT_PRINCIPAL_KRW, get_periods
from lastofus.core.account import Account
from lastofus.data.loader import fetch_ohlcv
from lastofus.strategy.infinite_v22 import run_strategy, run_bah
from lastofus.backtest.metrics import compute_metrics


# ── 그리드 파라미터 정의 ────────────────────────────────────────────────────
SPLITS_GRID         = [20, 30, 40, 60]
PROFIT_TARGET_GRID  = [0.07, 0.10, 0.12, 0.15, 0.20]
REINVEST_RATIO_GRID = [0.0, 0.5, 1.0]

DEFAULT_TICKERS = ["TQQQ", "SOXL", "122630.KS"]
DEFAULT_PERIOD  = "3yr"


def run_sweep(tickers: list[str], period_key: str) -> dict:
    periods = get_periods()
    if period_key not in periods:
        print(f"ERROR: unknown period '{period_key}'. Available: {list(periods)}")
        sys.exit(1)
    start, end = periods[period_key]

    results: dict = {}

    for ticker in tickers:
        cfg = TICKER_CONFIG.get(ticker, {})
        principal = DEFAULT_PRINCIPAL_KRW if cfg.get("market") == "KR" else DEFAULT_PRINCIPAL_USD
        ticker_start = cfg.get("start_date", "2000-01-01")
        effective_start = max(start, ticker_start)

        try:
            df = fetch_ohlcv(ticker, effective_start, end)
        except Exception as exc:
            print(f"  {ticker}: data error — {exc}")
            continue

        if df is None or len(df) < 20:
            print(f"  {ticker}: insufficient data, skip")
            continue

        dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in df.index]
        _, eq_bah = run_bah(df, principal)
        m_bah = compute_metrics(eq_bah, dates)

        ticker_results: list[dict] = []
        combos = list(product(SPLITS_GRID, PROFIT_TARGET_GRID, REINVEST_RATIO_GRID))
        total = len(combos)

        print(f"  {ticker}: {total} combinations ...", flush=True)
        t0 = time.time()

        for splits, pt, rr in combos:
            acct = Account(principal=principal, splits=splits, reinvest_ratio=rr)
            try:
                _, equity = run_strategy(df, acct, pt)
                m = compute_metrics(equity, dates)
            except Exception:
                continue

            ticker_results.append({
                "splits":         splits,
                "profit_target":  pt,
                "reinvest_ratio": rr,
                "cagr":           m["cagr"],
                "mdd":            m["mdd"],
                "sharpe":         m["sharpe"],
                "sortino":        m["sortino"],
                "cycles":         acct.cycle_count,
                "quarter_cuts":   acct.quarter_cut_count,
                "bah_cagr":       m_bah["cagr"],
                "alpha":          m["cagr"] - m_bah["cagr"],
            })

        elapsed = time.time() - t0
        # Sort by CAGR descending
        ticker_results.sort(key=lambda x: x["cagr"], reverse=True)
        results[ticker] = {
            "period": period_key,
            "n_bars": len(df),
            "bah_cagr": m_bah["cagr"],
            "results": ticker_results,
            "best": ticker_results[0] if ticker_results else {},
        }
        best = ticker_results[0] if ticker_results else {}
        print(
            f"    Done in {elapsed:.1f}s | Best: splits={best.get('splits')} "
            f"target={best.get('profit_target'):.0%} rr={best.get('reinvest_ratio')} "
            f"CAGR={best.get('cagr', 0):.1%}"
        )

    return results


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="파라미터 그리드 탐색")
    p.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    p.add_argument("--period",  default=DEFAULT_PERIOD)
    p.add_argument("--output",  default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    print(f"Sweep: tickers={args.tickers}, period={args.period}")
    print(f"Grid: splits={SPLITS_GRID}, targets={PROFIT_TARGET_GRID}, reinvest={REINVEST_RATIO_GRID}")
    print()

    results = run_sweep(args.tickers, args.period)

    out_path = Path(args.output) if args.output else Path("reports/data/sweep_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSweep results → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
