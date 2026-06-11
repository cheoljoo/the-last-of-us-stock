"""Performance metrics computed from an equity curve."""
from __future__ import annotations

import math
from typing import Any

import numpy as np


def compute_metrics(
    equity: list[float],
    dates: list | None = None,
    risk_free_rate: float = 0.02,
) -> dict[str, Any]:
    """Compute key metrics from a daily equity curve.

    Parameters
    ----------
    equity          Daily portfolio values (one per trading day).
    dates           Optional list of dates (same length as equity).
    risk_free_rate  Annual risk-free rate (default 2 %).

    Returns
    -------
    dict with keys: cagr, mdd, sharpe, sortino, total_return,
                    final_equity, n_days, start_equity.
    """
    if not equity or len(equity) < 2:
        return _empty_metrics()

    arr = np.array(equity, dtype=float)
    # Replace NaN/Inf with forward-fill
    mask = ~np.isfinite(arr)
    if mask.any():
        arr = _ffill(arr)

    if arr[0] <= 0 or not np.isfinite(arr[0]):
        return _empty_metrics()

    n_days = len(arr)
    n_years = n_days / 252.0

    start = arr[0]
    end   = arr[-1]

    # Total return
    total_return = (end - start) / start

    # CAGR
    if n_years > 0 and end > 0 and start > 0:
        cagr = (end / start) ** (1.0 / n_years) - 1.0
    else:
        cagr = 0.0

    # Max Drawdown
    peak = np.maximum.accumulate(arr)
    dd   = (arr - peak) / peak
    mdd  = float(dd.min())

    # Daily returns
    daily_ret = np.diff(arr) / arr[:-1]
    daily_ret = daily_ret[np.isfinite(daily_ret)]

    # Sharpe
    rf_daily = (1 + risk_free_rate) ** (1 / 252) - 1
    excess   = daily_ret - rf_daily
    if len(excess) > 1 and excess.std() > 0:
        sharpe = float(excess.mean() / excess.std() * math.sqrt(252))
    else:
        sharpe = 0.0

    # Sortino  (downside deviation)
    neg = excess[excess < 0]
    if len(neg) > 1 and neg.std() > 0:
        sortino = float(excess.mean() / neg.std() * math.sqrt(252))
    else:
        sortino = 0.0

    return {
        "cagr":          round(cagr, 6),
        "mdd":           round(mdd, 6),
        "sharpe":        round(sharpe, 4),
        "sortino":       round(sortino, 4),
        "total_return":  round(total_return, 6),
        "final_equity":  round(float(end), 4),
        "start_equity":  round(float(start), 4),
        "n_days":        n_days,
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "cagr":         0.0,
        "mdd":          0.0,
        "sharpe":       0.0,
        "sortino":      0.0,
        "total_return": 0.0,
        "final_equity": 0.0,
        "start_equity": 0.0,
        "n_days":       0,
    }


def _ffill(arr: np.ndarray) -> np.ndarray:
    """Forward-fill NaN/Inf values in a 1-D array."""
    out = arr.copy()
    for i in range(1, len(out)):
        if not np.isfinite(out[i]):
            out[i] = out[i - 1]
    return out
