from datetime import date, timedelta
from typing import Any

TICKER_CONFIG: dict[str, dict[str, Any]] = {
    # ── US 3x leverage ──────────────────────────────────────────────────────
    "TQQQ": {
        "name": "ProShares UltraPro QQQ (3x 나스닥100)",
        "market": "US", "leverage": 3,
        "profit_target": 0.10,      # V2.2
        "profit_target_v30": 0.15,  # V3.0
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2010-02-11",
    },
    "SPXL": {
        "name": "Direxion S&P500 Bull 3x",
        "market": "US", "leverage": 3,
        "profit_target": 0.10, "profit_target_v30": 0.15,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2008-11-05",
    },
    "UPRO": {
        "name": "ProShares UltraPro S&P500 (3x)",
        "market": "US", "leverage": 3,
        "profit_target": 0.10, "profit_target_v30": 0.15,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2009-06-25",
    },
    "SOXL": {
        "name": "Direxion Semiconductor Bull 3x (반도체)",
        "market": "US", "leverage": 3,
        "profit_target": 0.10, "profit_target_v30": 0.20,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2010-03-11",
    },
    # ── US 1x benchmark ─────────────────────────────────────────────────────
    "QQQ": {
        "name": "Invesco QQQ (1x 나스닥100)",
        "market": "US", "leverage": 1,
        "profit_target": 0.10, "profit_target_v30": 0.10,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "1999-03-10",
    },
    "VOO": {
        "name": "Vanguard S&P500 ETF (1x)",
        "market": "US", "leverage": 1,
        "profit_target": 0.10, "profit_target_v30": 0.10,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2010-09-09",
    },
    # ── KR 2x leverage ──────────────────────────────────────────────────────
    "122630.KS": {
        "name": "KODEX 레버리지 (2x KOSPI200)",
        "market": "KR", "leverage": 2,
        "profit_target": 0.07, "profit_target_v30": 0.10,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2010-02-22",
    },
    "233740.KS": {
        "name": "KODEX 코스닥150 레버리지 (2x)",
        "market": "KR", "leverage": 2,
        "profit_target": 0.07, "profit_target_v30": 0.10,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2015-09-07",
    },
    # ── KR 1x benchmark ─────────────────────────────────────────────────────
    "069500.KS": {
        "name": "KODEX 200 (1x KOSPI200)",
        "market": "KR", "leverage": 1,
        "profit_target": 0.07, "profit_target_v30": 0.07,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2002-10-14",
    },
    "229200.KS": {
        "name": "KODEX 코스닥150 (1x)",
        "market": "KR", "leverage": 1,
        "profit_target": 0.07, "profit_target_v30": 0.07,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2015-09-07",
    },
    # ── 금 ETF ──────────────────────────────────────────────────────────────
    "GLD": {
        "name": "SPDR Gold Shares (금 ETF)",
        "market": "US", "leverage": 1,
        "profit_target": 0.10, "profit_target_v30": 0.10,
        "splits": 40, "splits_v30": 20, "splits_v4": 40,
        "start_date": "2004-11-18",
    },
}

TICKER_GROUPS = {
    "US 3x 레버리지": ["TQQQ", "SPXL", "UPRO", "SOXL"],
    "US 1x 벤치마크": ["QQQ", "VOO"],
    "금 ETF": ["GLD"],
    "KR 2x 레버리지": ["122630.KS", "233740.KS"],
    "KR 1x 벤치마크": ["069500.KS", "229200.KS"],
}

# 멀티에셋 VR 포트폴리오 정의
# weights: {ticker: fraction}, sum must equal 1.0
MULTI_VR_CONFIGS: list[dict] = [
    # ── 단일 종목 100% (비교 기준) ────────────────────────────────────────
    {
        "id":      "QQQ100",
        "name":    "QQQ 100%",
        "weights": {"QQQ": 1.00},
    },
    {
        "id":      "VOO100",
        "name":    "VOO 100%",
        "weights": {"VOO": 1.00},
    },
    {
        "id":      "GLD100",
        "name":    "금(GLD) 100%",
        "weights": {"GLD": 1.00},
    },
    # ── 혼합 포트폴리오 ────────────────────────────────────────────────────
    {
        "id":      "QQQ30_VOO40_GLD30",
        "name":    "QQQ 30% + VOO 40% + 금 30%",
        "weights": {"QQQ": 0.30, "VOO": 0.40, "GLD": 0.30},
    },
    {
        "id":      "QQQ50_VOO50",
        "name":    "QQQ 50% + VOO 50%",
        "weights": {"QQQ": 0.50, "VOO": 0.50},
    },
    {
        "id":      "QQQ50_GLD50",
        "name":    "QQQ 50% + 금 50%",
        "weights": {"QQQ": 0.50, "GLD": 0.50},
    },
    {
        "id":      "VOO50_GLD50",
        "name":    "VOO 50% + 금 50%",
        "weights": {"VOO": 0.50, "GLD": 0.50},
    },
]

# VR default parameters
VR_DEFAULTS = {
    "slope": 11,          # G: V목표 성장 속도 (10~13)
    "band_pct": 0.08,     # ±8% 밴드
    "deposit_per_cycle": 200.0,  # 2주마다 풀에 추가 (USD 기준)
    "cycle_days": 10,     # 10 거래일 = 2주
    "equity_frac": 0.75,  # 초기 주식 비중 75%, 현금 풀 25%
}

# VR 5.0 (오피셜 공식) 기본 파라미터
# 출처: https://quantstack.app/vr/overview/ (핵심 용어&공식), /vr/procedure/
# next V = V + Pool/G + 적립금(or -인출금), 밴드 ±15% 오피셜, Pool 사용 한도는 유형별
VR5_DEFAULTS = {
    "g_installment": 10,     # 적립식 권장 시작 G
    "g_lumpsum": 10,         # 거치식 권장 시작 G
    "g_withdrawal": 20,      # 인출식 권장 시작 G
    "band_pct": 0.15,        # ±15% 오피셜 밴드
    "cycle_days": 10,        # 2주 = 10거래일
    "equity_frac": 0.75,     # 초기 주식:Pool = 75:25
    "cycle_amount": 200.0,   # 사이클당 적립/인출 금액 (USD 기준)
    "pool_limit": {"installment": 0.75, "lumpsum": 0.50, "withdrawal": 0.25},
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
        "covid_crash":    ("2019-10-01", "2020-04-30"),   # VOO MDD -34% (코로나 폭락)
        "dotcom_2001":    ("2000-10-01", "2001-04-30"),   # QQQ MDD -61% (닷컴 버블 붕괴)
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
        "covid_crash":    "코로나 폭락 6M (VOO -34%)",
        "dotcom_2001":    "닷컴 버블 6M (QQQ -61%)",
        "bull_2013_2019": "2013-2019 강세장",
        "full":           "전체 구간",
    }


# 하위호환 — 기존 코드에서 PERIOD_LABELS 직접 참조하는 곳 대응
PERIOD_LABELS = get_period_labels()

# Default principal amounts
DEFAULT_PRINCIPAL_USD = 10_000.0
DEFAULT_PRINCIPAL_KRW = 10_000_000.0
