"""Persist / load backtest results as JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_DEFAULT_PATH = Path(__file__).parents[3] / "reports" / "data" / "results.json"


def save_results(data: dict[str, Any], path: str | Path | None = None) -> Path:
    """Serialise *data* to JSON at *path* (default: reports/data/results.json).

    Returns the resolved Path that was written.
    """
    target = Path(path) if path else _DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    with open(target, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=_json_default)

    return target


def load_results(path: str | Path | None = None) -> dict[str, Any]:
    """Load JSON results from *path* (default: reports/data/results.json).

    Returns an empty dict if the file does not exist.
    """
    target = Path(path) if path else _DEFAULT_PATH
    if not target.exists():
        return {}

    with open(target, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _json_default(obj: Any) -> Any:
    """Fallback serialiser for types not handled natively by json."""
    import numpy as np
    import pandas as pd

    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return str(obj.date())
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")
