#!/usr/bin/env python
"""복합 포트폴리오 시뮬레이션 — VR 70% + 무한매수법 30%.

Usage:
    uv run python scripts/run_portfolio_sim.py [--ticker TQQQ] [--period 5yr]
    uv run python scripts/run_portfolio_sim.py --ticker TQQQ --period full

출력: reports/data/portfolio_results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from lastofus.config import TICKER_CONFIG, DEFAULT_PRINCIPAL_USD, get_periods, VR_DEFAULTS
from lastofus.core.account import Account
from lastofus.data.loader import fetch_ohlcv
from lastofus.strategy.infinite_v22 import run_strategy, run_bah
from lastofus.strategy.value_rebalancing import run_vr
from lastofus.backtest.metrics import compute_metrics

# 포트폴리오 시나리오 정의
SCENARIOS = [
    {"name": "공격형 (VR 70% + 무매 30%)",  "vr_frac": 0.70, "inf_frac": 0.30, "vr_slope": 12},
    {"name": "균형형 (VR 80% + 무매 20%)",  "vr_frac": 0.80, "inf_frac": 0.20, "vr_slope": 11},
    {"name": "보수형 (VR 90% + 무매 10%)",  "vr_frac": 0.90, "inf_frac": 0.10, "vr_slope": 10},
    {"name": "인출식 VR 100%",              "vr_frac": 1.00, "inf_frac": 0.00, "vr_slope": 11,
     "withdrawal_per_cycle": 500.0},  # 2주마다 $500 인출
]

TOTAL_PRINCIPAL = 100_000.0   # 총 투자 원금 $100,000


def run_portfolio(ticker: str, period_key: str) -> dict:
    cfg = TICKER_CONFIG.get(ticker, {})
    periods = get_periods()
    if period_key not in periods:
        return {}
    start, end = periods[period_key]
    ticker_start = cfg.get("start_date", "2000-01-01")
    effective_start = max(start, ticker_start)
    profit_target = cfg.get("profit_target", 0.10)
    splits = cfg.get("splits", 40)

    try:
        df = fetch_ohlcv(ticker, effective_start, end)
    except Exception as exc:
        return {"error": str(exc)}

    if df is None or len(df) < 20:
        return {"error": "insufficient data"}

    dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in df.index]

    # B&H benchmark for full principal
    _, eq_bah = run_bah(df, TOTAL_PRINCIPAL)
    m_bah = compute_metrics(eq_bah, dates)

    scenario_results = []

    for sc in SCENARIOS:
        vr_principal  = TOTAL_PRINCIPAL * sc["vr_frac"]
        inf_principal = TOTAL_PRINCIPAL * sc["inf_frac"]
        withdrawal    = sc.get("withdrawal_per_cycle", 0.0)

        # VR leg
        _, eq_vr, _, _ = run_vr(
            df, vr_principal,
            slope=sc["vr_slope"],
            band_pct=VR_DEFAULTS["band_pct"],
            deposit_per_cycle=-withdrawal,   # negative = withdrawal
            cycle_days=VR_DEFAULTS["cycle_days"],
            equity_frac=VR_DEFAULTS["equity_frac"],
        )

        # Infinite buying leg
        eq_inf = [0.0] * len(dates)
        if inf_principal > 0:
            acct = Account(principal=inf_principal, splits=splits, reinvest_ratio=0.5)
            _, eq_inf = run_strategy(df, acct, profit_target)

        # Combined equity
        eq_combined = [
            (eq_vr[i] if i < len(eq_vr) else 0) +
            (eq_inf[i] if i < len(eq_inf) else 0)
            for i in range(len(dates))
        ]

        m_combined = compute_metrics(eq_combined, dates)
        m_inf = compute_metrics(eq_inf, dates)
        m_vr  = compute_metrics(eq_vr,  dates)

        scenario_results.append({
            "scenario":       sc["name"],
            "vr_frac":        sc["vr_frac"],
            "inf_frac":       sc["inf_frac"],
            "vr_slope":       sc["vr_slope"],
            "withdrawal_per_cycle": withdrawal,
            "metrics_combined": m_combined,
            "metrics_vr":       m_vr,
            "metrics_inf":      m_inf,
            "equity_combined":  _thin(eq_combined, 1000),
            "equity_vr":        _thin(eq_vr, 1000),
            "equity_inf":       _thin(eq_inf, 1000),
        })
        print(
            f"  {sc['name']:30s}  "
            f"CAGR={m_combined['cagr']:.1%}  "
            f"MDD={m_combined['mdd']:.1%}"
        )

    return {
        "ticker": ticker, "period": period_key,
        "total_principal": TOTAL_PRINCIPAL,
        "dates": _thin(dates, 1000),
        "bah_cagr": m_bah["cagr"],
        "equity_bah": _thin(eq_bah, 1000),
        "scenarios": scenario_results,
    }


def _thin(lst: list, n: int) -> list:
    if len(lst) <= n:
        return lst
    step = len(lst) / n
    idx = [int(i * step) for i in range(n)]
    idx[-1] = len(lst) - 1
    return [lst[i] for i in idx]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="복합 포트폴리오 시뮬레이션")
    p.add_argument("--ticker", default="TQQQ")
    p.add_argument("--period", default="5yr")
    p.add_argument("--output", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    print(f"Portfolio sim: {args.ticker} / {args.period}")
    print(f"Total principal: ${TOTAL_PRINCIPAL:,.0f}")
    print()

    result = run_portfolio(args.ticker, args.period)

    out_path = Path(args.output) if args.output else Path("reports/data/portfolio_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nPortfolio results → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
