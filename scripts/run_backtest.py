#!/usr/bin/env python
"""Run the 라오어 무한매수법 V2.2 backtest for all (or selected) tickers × periods.

Usage:
    uv run python scripts/run_backtest.py [--fetch] [--tickers TQQQ SPXL] [--periods 3yr 5yr]

Options:
    --fetch              Download / refresh market data before running
    --tickers T1 T2 …    Only backtest these tickers (default: all)
    --periods P1 P2 …    Only these period keys (default: all)
    --principal AMOUNT   Override principal (USD for US, KRW for KR)
    --output PATH        Override output JSON path
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running from repo root without installation
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from lastofus.config import TICKER_CONFIG, get_periods, PERIOD_LABELS
from lastofus.data.loader import refresh_all
from lastofus.backtest.engine import run_all
from lastofus.backtest.report import save_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="라오어 무한매수법 V2.2 백테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download / refresh all market data before running backtest",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        metavar="TICKER",
        default=None,
        help="Specific tickers to backtest (default: all configured tickers)",
    )
    parser.add_argument(
        "--periods",
        nargs="+",
        metavar="PERIOD",
        default=None,
        help="Period keys to run (default: all). Available: " + ", ".join(get_periods().keys()),
    )
    parser.add_argument(
        "--principal",
        type=float,
        default=None,
        help="Override default principal amount",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write results JSON (default: reports/data/results.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    all_tickers = list(TICKER_CONFIG.keys())
    all_periods = get_periods()

    # Resolve tickers
    tickers = args.tickers if args.tickers else all_tickers
    unknown = [t for t in tickers if t not in TICKER_CONFIG]
    if unknown:
        print(f"WARNING: Unknown tickers (will attempt anyway): {unknown}")

    # Resolve periods
    if args.periods:
        periods = {k: v for k, v in all_periods.items() if k in args.periods}
        missing_periods = [p for p in args.periods if p not in all_periods]
        if missing_periods:
            print(f"WARNING: Unknown period keys ignored: {missing_periods}")
    else:
        periods = all_periods

    if not periods:
        print("ERROR: No valid periods selected.", file=sys.stderr)
        return 1

    print("=" * 60)
    print("라오어 무한매수법 V2.2 — 백테스트")
    print("=" * 60)
    print(f"Tickers : {', '.join(tickers)}")
    print(f"Periods : {', '.join(f'{k}({PERIOD_LABELS.get(k, k)})' for k in periods)}")
    if args.principal:
        print(f"Principal: {args.principal:,.0f}")
    print()

    # ------------------------------------------------------------------
    # 1. Fetch data
    # ------------------------------------------------------------------
    if args.fetch:
        print("--- Downloading market data ---")
        refresh_all(tickers)
        print()

    # ------------------------------------------------------------------
    # 2. Run backtest
    # ------------------------------------------------------------------
    print("--- Running backtest ---")
    t0 = time.time()
    results = run_all(
        tickers=tickers,
        periods=periods,
        principal=args.principal,
    )
    elapsed = time.time() - t0
    print(f"\nBacktest complete in {elapsed:.1f}s")

    # ------------------------------------------------------------------
    # 3. Save results
    # ------------------------------------------------------------------
    output_path = args.output
    saved_path = save_results(results, output_path)
    print(f"Results saved → {saved_path}")

    # ------------------------------------------------------------------
    # 4. Quick summary
    # ------------------------------------------------------------------
    print()
    print("--- Quick Summary ---")
    header = f"{'Ticker':<15} {'Period':<18} {'CAGR':>8} {'MDD':>8} {'Sharpe':>7} {'Cycles':>7}"
    print(header)
    print("-" * len(header))
    for ticker in tickers:
        for period_key in periods:
            r = results.get(ticker, {}).get(period_key, {})
            if r.get("skip"):
                print(f"{ticker:<15} {PERIOD_LABELS.get(period_key, period_key):<18}   {'데이터 없음':>20}")
                continue
            ms = r.get("metrics_strategy", {})
            print(
                f"{ticker:<15} {PERIOD_LABELS.get(period_key, period_key):<18} "
                f"{ms.get('cagr', 0)*100:>7.1f}% "
                f"{ms.get('mdd', 0)*100:>7.1f}% "
                f"{ms.get('sharpe', 0):>7.2f} "
                f"{r.get('final_cycles', 0):>7}"
            )

    print()
    print(f"Next step: uv run python scripts/generate_dashboard.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
