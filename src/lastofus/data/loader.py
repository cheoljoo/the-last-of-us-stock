"""OHLCV data loader with parquet caching via yfinance."""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).parents[3] / "data" / "cache"


def fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Return OHLCV DataFrame for *ticker* sliced to [start, end].

    Data is cached as parquet in data/cache/. The cache stores the full
    history; slicing happens on every call so a single cache file serves
    all period queries.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{ticker.replace('.', '_')}.parquet"

    if cache_file.exists():
        try:
            df = pd.read_parquet(cache_file)
        except Exception:
            # Corrupt cache — re-download
            df = _download(ticker)
            if not df.empty:
                df.to_parquet(cache_file)
    else:
        df = _download(ticker)
        if not df.empty:
            df.to_parquet(cache_file)

    if df.empty:
        return df

    df.index = pd.to_datetime(df.index)
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
    return df[mask].copy()


def refresh_all(tickers: list[str]) -> None:
    """Force re-download for every ticker and overwrite cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for ticker in tickers:
        print(f"  Fetching {ticker}...", end=" ", flush=True)
        try:
            df = _download(ticker)
            if not df.empty:
                cache_file = CACHE_DIR / f"{ticker.replace('.', '_')}.parquet"
                df.to_parquet(cache_file)
                print(f"OK ({len(df)} rows)")
            else:
                print("EMPTY — no data returned")
        except Exception as exc:
            print(f"ERROR: {exc}")


def _download(ticker: str) -> pd.DataFrame:
    """Download full history for *ticker* from 2000-01-01 onward."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = yf.download(
            ticker,
            start="2000-01-01",
            auto_adjust=True,
            progress=False,
            actions=False,
        )

    if data is None or data.empty:
        return pd.DataFrame()

    # yfinance sometimes returns MultiIndex columns (ticker, field)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    needed = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]
    if not needed:
        return pd.DataFrame()

    df = data[needed].copy()
    df.index = pd.to_datetime(df.index)
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    # Drop rows where Close is NaN
    df = df.dropna(subset=["Close"])
    return df


def get_latest_price(ticker: str) -> float | None:
    """Return the most recent closing price for *ticker* (live fetch)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", auto_adjust=True)
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None
