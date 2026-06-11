#!/usr/bin/env python
"""Generate the self-contained HTML dashboard from backtest results.

Usage:
    uv run python scripts/generate_dashboard.py [--input PATH] [--output DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from lastofus.backtest.report import load_results
from lastofus.reports.render import generate_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="라오어 무한매수법 대시보드 생성",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to results.json (default: reports/data/results.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for HTML (default: reports/html/)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Load results
    input_path = args.input
    print(f"Loading results from: {input_path or 'reports/data/results.json'}")
    results = load_results(input_path)

    if not results:
        print(
            "ERROR: No results found. Run the backtest first:\n"
            "  uv run python scripts/run_backtest.py",
            file=sys.stderr,
        )
        return 1

    n_tickers  = len(results)
    n_results  = sum(
        1 for td in results.values()
        for r in td.values()
        if not r.get("skip")
    )
    print(f"Found results for {n_tickers} tickers, {n_results} ticker-period combinations")

    # Generate dashboard
    output_dir = Path(args.output) if args.output else None
    print("Generating dashboard...")
    out_file = generate_dashboard(results, output_dir)

    size_kb = out_file.stat().st_size / 1024
    print(f"\nDashboard generated: {out_file} ({size_kb:.0f} KB)")
    print(f"\nOpen in browser:")
    print(f"  file://{out_file.resolve()}")
    print()
    print("Or publish with:")
    print("  make publish")

    return 0


if __name__ == "__main__":
    sys.exit(main())
