"""Backtest engine – orchestrates data loading, strategy runs, and metrics."""
from __future__ import annotations

from typing import Any

import pandas as pd

from lastofus.config import (
    TICKER_CONFIG,
    MULTI_VR_CONFIGS,
    VR_DEFAULTS,
    VR5_DEFAULTS,
    DEFAULT_PRINCIPAL_USD,
    DEFAULT_PRINCIPAL_KRW,
    get_periods,
)
from lastofus.core.account import Account
from lastofus.data.loader import fetch_ohlcv
from lastofus.strategy.infinite_v22 import run_strategy, run_bah, run_dca, run_monthly_dca
from lastofus.strategy.infinite_v30 import run_strategy_v30
from lastofus.strategy.infinite_v4 import run_strategy_v4
from lastofus.strategy.value_rebalancing import run_vr, run_vr_monthly, run_vr_multi_asset
from lastofus.strategy.value_rebalancing_v5 import run_vr5
from lastofus.backtest.metrics import compute_metrics

MIN_BARS = 20


# ---------------------------------------------------------------------------
# Single ticker × period — V2.2
# ---------------------------------------------------------------------------

def run_single(
    ticker: str,
    period_key: str,
    start: str,
    end: str,
    principal: float | None = None,
    reinvest_ratio: float = 0.0,
) -> dict[str, Any] | None:
    """Run V2.2 + V3.0 + VR for one ticker × one period.

    Returns a result dict containing all three strategies, or None if
    there is insufficient data.
    """
    cfg = TICKER_CONFIG.get(ticker, {})
    if principal is None:
        principal = DEFAULT_PRINCIPAL_KRW if cfg.get("market") == "KR" else DEFAULT_PRINCIPAL_USD

    profit_target: float = cfg.get("profit_target", 0.10)
    profit_target_v30: float = cfg.get("profit_target_v30", profit_target)
    splits: int = cfg.get("splits", 40)
    splits_v30: int = cfg.get("splits_v30", 20)
    splits_v4: int = cfg.get("splits_v4", 40)

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

    # ── V2.2 Strategy ─────────────────────────────────────────────────────
    acct_v22 = Account(principal=principal, splits=splits, reinvest_ratio=reinvest_ratio)
    trades_v22, equity_v22 = run_strategy(df, acct_v22, profit_target)

    # ── V3.0 Strategy ─────────────────────────────────────────────────────
    acct_v30 = Account(principal=principal, splits=splits_v30, reinvest_ratio=reinvest_ratio)
    trades_v30, equity_v30 = run_strategy_v30(df, acct_v30, profit_target_v30)

    # ── V4.0 Strategy (일반모드 ⇄ 리버스모드, profit_target은 V3.0과 동일값 재사용) ──
    acct_v4 = Account(principal=principal, splits=splits_v4, reinvest_ratio=reinvest_ratio)
    trades_v4, equity_v4 = run_strategy_v4(df, acct_v4, profit_target_v30)

    # ── V5.0 VR (오피셜 공식: next V = V + Pool/G + 적립금) ───────────────
    vr5_p = VR5_DEFAULTS
    vr5_deposit = principal * 0.02 if cfg.get("market") == "KR" else vr5_p["cycle_amount"]
    _, equity_vr5, v5_curve, invested_vr5 = run_vr5(
        df, principal,
        g=vr5_p["g_installment"],
        band_pct=vr5_p["band_pct"],
        mode="installment",
        cycle_amount=vr5_deposit,
        cycle_days=vr5_p["cycle_days"],
        equity_frac=vr5_p["equity_frac"],
    )

    # ── VR Strategy (2주 고정 사이클 적립) ───────────────────────────────
    vr_p = VR_DEFAULTS.copy()
    if cfg.get("market") == "KR":
        deposit = principal * 0.02
    else:
        deposit = vr_p["deposit_per_cycle"]

    _, equity_vr, v_curve, invested_vr = run_vr(
        df, principal,
        slope=vr_p["slope"],
        band_pct=vr_p["band_pct"],
        deposit_per_cycle=deposit,
        cycle_days=vr_p["cycle_days"],
        equity_frac=vr_p["equity_frac"],
    )

    # ── Monthly DCA benchmark (적립식) ───────────────────────────────────
    _, equity_monthly_dca, invested_monthly_dca = run_monthly_dca(df, principal)

    # ── Monthly DCA + VR (적립식 VR) ─────────────────────────────────────
    _, equity_monthly_vr, v_curve_mvr, invested_monthly_vr = run_vr_monthly(
        df, principal,
        slope=vr_p["slope"],
        band_pct=vr_p["band_pct"],
        cycle_days=vr_p["cycle_days"],
        equity_frac=vr_p["equity_frac"],
    )

    # ── Benchmarks ────────────────────────────────────────────────────────
    _, equity_bah = run_bah(df, principal)
    _, equity_dca = run_dca(df, principal, splits)

    # ── Metrics ───────────────────────────────────────────────────────────
    metrics_v22  = compute_metrics(equity_v22,  dates, total_invested=principal)
    metrics_v30  = compute_metrics(equity_v30,  dates, total_invested=principal)
    metrics_v4   = compute_metrics(equity_v4,   dates, total_invested=principal)
    metrics_vr5  = compute_metrics(equity_vr5,  dates, total_invested=invested_vr5)
    metrics_vr   = compute_metrics(equity_vr,   dates, total_invested=invested_vr)
    metrics_bah  = compute_metrics(equity_bah,  dates, total_invested=principal)
    metrics_dca  = compute_metrics(equity_dca,  dates, total_invested=principal)
    metrics_mdca = compute_metrics(equity_monthly_dca, dates, total_invested=invested_monthly_dca)
    metrics_mvr  = compute_metrics(equity_monthly_vr,  dates, total_invested=invested_monthly_vr)

    last_close = float(df["Close"].iloc[-1])

    return {
        "ticker":       ticker,
        "ticker_name":  cfg.get("name", ticker),
        "market":       cfg.get("market", "US"),
        "leverage":     cfg.get("leverage", 1),
        "period":       period_key,
        "start":        dates[0] if dates else effective_start,
        "end":          dates[-1] if dates else end,
        "n_bars":       len(df),
        "principal":    principal,

        # ── V2.2 (primary strategy, backwards-compatible keys) ──────────
        "profit_target":   profit_target,
        "splits":          splits,
        "metrics_strategy": metrics_v22,
        "metrics_bah":      metrics_bah,
        "metrics_dca":      metrics_dca,
        "final_cycles":       acct_v22.cycle_count,
        "final_quarter_cuts": acct_v22.quarter_cut_count,
        "final_equity":       acct_v22.equity(last_close),
        "final_cash":         acct_v22.cash,
        "final_shares":       acct_v22.shares,
        "final_avg_price":    acct_v22.avg_price,
        "final_rounds_done":  acct_v22.rounds_done,
        "dates":              _thin(dates, 1500),
        "equity_strategy":    _thin(equity_v22, 1500),
        "equity_bah":         _thin(equity_bah, 1500),
        "equity_dca":         _thin(equity_dca, 1500),
        "trades":             trades_v22[-200:],

        # ── V3.0 ─────────────────────────────────────────────────────────
        "v30": {
            "profit_target":      profit_target_v30,
            "splits":             splits_v30,
            "metrics":            metrics_v30,
            "final_cycles":       acct_v30.cycle_count,
            "final_quarter_cuts": acct_v30.quarter_cut_count,
            "final_equity":       acct_v30.equity(last_close),
            "equity":             _thin(equity_v30, 1500),
            "trades":             trades_v30[-200:],
        },

        # ── V4.0 (일반모드 ⇄ 리버스모드 자동 전환) ──────────────────────────
        "v4": {
            "profit_target":      profit_target_v30,
            "splits":             splits_v4,
            "metrics":            metrics_v4,
            "final_cycles":       acct_v4.cycle_count,
            "final_quarter_cuts": acct_v4.quarter_cut_count,
            "final_equity":       acct_v4.equity(last_close),
            "equity":             _thin(equity_v4, 1500),
            "trades":             trades_v4[-200:],
        },

        # ── V5.0 VR (오피셜 공식: next V = V + Pool/G + 적립금) ────────────
        "vr5": {
            "g":              vr5_p["g_installment"],
            "band_pct":       vr5_p["band_pct"],
            "deposit":        vr5_deposit,
            "total_invested": invested_vr5,
            "metrics":        metrics_vr5,
            "equity":         _thin(equity_vr5, 1500),
            "v_curve":        _thin(v5_curve, 1500),
        },

        # ── VR (2주 고정 사이클 적립) ─────────────────────────────────────
        "vr": {
            "slope":          vr_p["slope"],
            "band_pct":       vr_p["band_pct"],
            "deposit":        deposit,
            "total_invested": invested_vr,
            "metrics":        metrics_vr,
            "equity":         _thin(equity_vr, 1500),
            "v_curve":        _thin(v_curve, 1500),
        },

        # ── 적립식 DCA (매월 초) ──────────────────────────────────────────
        "monthly_dca": {
            "total_invested": invested_monthly_dca,
            "metrics":        metrics_mdca,
            "equity":         _thin(equity_monthly_dca, 1500),
        },

        # ── 적립식 VR (매월 초 + 2주 리밸런싱) ───────────────────────────
        "monthly_vr": {
            "slope":          vr_p["slope"],
            "band_pct":       vr_p["band_pct"],
            "total_invested": invested_monthly_vr,
            "metrics":        metrics_mvr,
            "equity":         _thin(equity_monthly_vr, 1500),
            "v_curve":        _thin(v_curve_mvr, 1500),
        },
    }


# ---------------------------------------------------------------------------
# Run all tickers × periods
# ---------------------------------------------------------------------------

def run_all(
    tickers: list[str] | None = None,
    periods: dict[str, tuple[str, str]] | None = None,
    principal: float | None = None,
    reinvest_ratio: float = 0.0,
) -> dict[str, Any]:
    """Run all strategies for every ticker × period combination."""
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
                res = run_single(ticker, period_key, start, end, p, reinvest_ratio)
                if res is None:
                    print("SKIP (insufficient data)")
                    results[ticker][period_key] = {"skip": True, "reason": "데이터 없음"}
                else:
                    v22  = res["metrics_strategy"]
                    v30  = res["v30"]["metrics"]
                    v4   = res["v4"]["metrics"]
                    vr5  = res["vr5"]["metrics"]
                    vr   = res["vr"]["metrics"]
                    mdca = res["monthly_dca"]["metrics"]
                    mvr  = res["monthly_vr"]["metrics"]
                    print(
                        f"V2.2={v22['cagr_on_invested']:.1%}  "
                        f"V3.0={v30['cagr_on_invested']:.1%}  "
                        f"V4.0={v4['cagr_on_invested']:.1%}  "
                        f"VR5.0={vr5['cagr_on_invested']:.1%}  "
                        f"VR={vr['cagr_on_invested']:.1%}  "
                        f"月DCA={mdca['cagr_on_invested']:.1%}  "
                        f"月VR={mvr['cagr_on_invested']:.1%}"
                    )
                    results[ticker][period_key] = res
            except Exception as exc:
                print(f"ERROR: {exc}")
                results[ticker][period_key] = {"skip": True, "reason": str(exc)}

    return results


# ---------------------------------------------------------------------------
# Multi-asset VR
# ---------------------------------------------------------------------------

def run_multi_vr_periods(
    periods: dict[str, tuple[str, str]] | None = None,
    principal: float = DEFAULT_PRINCIPAL_USD,
) -> dict[str, Any]:
    """Run all MULTI_VR_CONFIGS × all periods.

    Returns
    -------
    {
      "QQQ30_VOO40_GLD30": {
          "name": "QQQ 30% + VOO 40% + 금 30%",
          "weights": {...},
          "3yr": {"metrics": {...}, "equity": [...], "dates": [...], "skip": False},
          ...
      },
      ...
    }
    """
    if periods is None:
        periods = get_periods()

    vr_p = VR_DEFAULTS.copy()

    # Collect all unique tickers needed
    needed: set[str] = set()
    for cfg in MULTI_VR_CONFIGS:
        needed.update(cfg["weights"].keys())

    results: dict[str, Any] = {}

    for cfg in MULTI_VR_CONFIGS:
        pid = cfg["id"]
        results[pid] = {"name": cfg["name"], "weights": cfg["weights"]}

        for period_key, (start, end) in periods.items():
            # Find effective start (latest start_date among tickers)
            effective_start = start
            for t in cfg["weights"]:
                t_start = TICKER_CONFIG.get(t, {}).get("start_date", "2000-01-01")
                effective_start = max(effective_start, t_start)

            try:
                dfs = {}
                for t in cfg["weights"]:
                    df = fetch_ohlcv(t, effective_start, end)
                    if df is not None and len(df) >= MIN_BARS:
                        dfs[t] = df

                if len(dfs) < len(cfg["weights"]):
                    results[pid][period_key] = {"skip": True, "reason": "데이터 부족"}
                    continue

                _, equity, v_curve, invested, dates = run_vr_multi_asset(
                    dfs, cfg["weights"], principal,
                    slope=vr_p["slope"],
                    band_pct=vr_p["band_pct"],
                    deposit_per_cycle=0.0,   # 추가 납입 없음 — 순수 리밸런싱 효과만
                    cycle_days=vr_p["cycle_days"],
                    equity_frac=vr_p["equity_frac"],
                )

                if not equity:
                    results[pid][period_key] = {"skip": True, "reason": "계산 실패"}
                    continue

                metrics = compute_metrics(equity, dates, total_invested=invested)
                results[pid][period_key] = {
                    "skip": False,
                    "metrics": metrics,
                    "equity": _thin(equity, 1500),
                    "dates":  _thin(dates, 1500),
                    "v_curve": _thin(v_curve, 1500),
                    "total_invested": invested,
                    "n_bars": len(equity),
                }

            except Exception as exc:
                results[pid][period_key] = {"skip": True, "reason": str(exc)}

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
    indices[-1] = n - 1
    return [lst[i] for i in indices]
