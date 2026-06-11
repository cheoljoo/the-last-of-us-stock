from datetime import date, timedelta
from typing import Any

TICKER_CONFIG: dict[str, dict[str, Any]] = {
    "TQQQ":       {"name": "ProShares UltraPro QQQ (3x 나스닥100)", "market": "US", "leverage": 3, "profit_target": 0.10, "splits": 40, "start_date": "2010-02-11"},
    "SPXL":       {"name": "Direxion S&P500 Bull 3x",               "market": "US", "leverage": 3, "profit_target": 0.10, "splits": 40, "start_date": "2008-11-05"},
    "UPRO":       {"name": "ProShares UltraPro S&P500 (3x)",         "market": "US", "leverage": 3, "profit_target": 0.10, "splits": 40, "start_date": "2009-06-25"},
    "QQQ":        {"name": "Invesco QQQ (1x 나스닥100)",              "market": "US", "leverage": 1, "profit_target": 0.10, "splits": 40, "start_date": "1999-03-10"},
    "VOO":        {"name": "Vanguard S&P500 ETF (1x)",               "market": "US", "leverage": 1, "profit_target": 0.10, "splits": 40, "start_date": "2010-09-09"},
    "122630.KS":  {"name": "KODEX 레버리지 (2x KOSPI200)",            "market": "KR", "leverage": 2, "profit_target": 0.07, "splits": 40, "start_date": "2010-02-22"},
    "233740.KS":  {"name": "KODEX 코스닥150 레버리지 (2x)",            "market": "KR", "leverage": 2, "profit_target": 0.07, "splits": 40, "start_date": "2015-09-07"},
    "069500.KS":  {"name": "KODEX 200 (1x KOSPI200)",                 "market": "KR", "leverage": 1, "profit_target": 0.07, "splits": 40, "start_date": "2002-10-14"},
    "229200.KS":  {"name": "KODEX 코스닥150 (1x)",                    "market": "KR", "leverage": 1, "profit_target": 0.07, "splits": 40, "start_date": "2015-09-07"},
}

TICKER_GROUPS = {
    "US 3x 레버리지": ["TQQQ", "SPXL", "UPRO"],
    "US 1x 벤치마크": ["QQQ", "VOO"],
    "KR 2x 레버리지": ["122630.KS", "233740.KS"],
    "KR 1x 벤치마크": ["069500.KS", "229200.KS"],
}


def get_periods() -> dict[str, tuple[str, str]]:
    today = date.today()
    this_year = today.year
    y3 = (today - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
    y5 = (today - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
    return {
        "this_year":      (f"{this_year}-01-01", today.strftime("%Y-%m-%d")),
        "3yr":            (y3,          today.strftime("%Y-%m-%d")),
        "5yr":            (y5,          today.strftime("%Y-%m-%d")),
        "2022":           ("2022-01-01", "2022-12-31"),
        "2020_covid":     ("2020-01-01", "2020-09-30"),
        "bull_2013_2019": ("2013-01-01", "2019-12-31"),
        "full":           ("2000-01-01", today.strftime("%Y-%m-%d")),
    }


def get_period_labels() -> dict[str, str]:
    """동적으로 올해 연도를 반영한 라벨 반환."""
    this_year = date.today().year
    return {
        "this_year":      f"{this_year}년 (올해)",
        "3yr":            "최근 3년",
        "5yr":            "최근 5년",
        "2022":           "2022 하락장",
        "2020_covid":     "2020 코로나",
        "bull_2013_2019": "2013-2019 강세장",
        "full":           "전체 구간",
    }


# 하위호환 — 기존 코드에서 PERIOD_LABELS 직접 참조하는 곳 대응
PERIOD_LABELS = get_period_labels()

# Default principal amounts
DEFAULT_PRINCIPAL_USD = 10_000.0
DEFAULT_PRINCIPAL_KRW = 10_000_000.0
