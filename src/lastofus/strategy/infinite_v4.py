"""무한매수법 V4.0 strategy implementation (일반모드 + 리버스모드 통합).

References
----------
- https://quantstack.app/infinite/v4-0-normal/   ("무한매수법 V4.0 · 일반모드", 발표일 2026-03-14,
  원글 posts/042(예고)·posts/043(일반모드))
- https://quantstack.app/infinite/v4-0-reverse/  ("무한매수법 V4.0 · 리버스모드", 발표일 2026-03-14,
  원글 posts/044, cafe.naver.com/infinitebuying/79264)

quantstack.app은 라오어(네이버 카페 "무한매수법 & 밸류리밸런싱 공부모임")가 공개한 방법론을
정리하는 비공식 3자 사이트이며, 위 두 페이지는 2026년 시점 최신 오피셜로 표기되어 있다.
방법론 자체의 저작권은 라오어에게 있고, 이 모듈은 해당 문서에 서술된 규칙을
일봉 단위 백테스트 엔진(OHLC 종가/고가 기반 체결 시뮬레이션)으로 옮긴 것이다.

V3.0 대비 핵심 변화 (일반모드, /vr/normal 문서 "핵심 변화 (vs V3.0)" 절)
------------------------------------------------------------------------
1. T 계산 단순화 — 매수누적액을 분할단가로 나누는 대신 매매 회차를 그대로 가산한다.
     · 1회 매수 완료 → T + 1        · 절반 매수 → T + 0.5
     · 쿼터매도 발생 → T × 0.75     · 사이클 종료(지정가매도) → T × 0.25로 이월 (0 리셋 아님)
2. 1회매수금 = 잔금 / (분할수 − T) — 매일 잔금·T가 바뀌므로 미세하게 변동한다.
   (V2.2/V3.0은 principal/splits 로 고정)
3. 매도 로직이 이원화된다 (문서 "매도 방법 (전·후반 공통)" 절):
     · 보유수량의 1/4 — 별지점에서 LOC 매도 ("쿼터매도"). 매도 후에도 사이클은 계속됨.
     · 나머지 3/4    — 고정 익절가(TQQQ +15% / SOXL +20%, ticker의 profit_target)에서
                        지정가 매도. 전량 소진되면 사이클 종료.
4. 원금 소진(T > 분할수 − 1) 시 V2.2/V3.0의 "쿼터컷"이 아니라 **리버스모드**
   (무한매도 + 쿼터매수, 문서 "발동 조건" 이하 전체)로 자동 전환된다.
   리버스모드는 종가가 평단 대비 −(profit_target)% 선을 넘어서면(TQQQ −15%/SOXL −20%)
   그 다음 거래일부터 일반모드로 복귀하며, 이때 T와 1회매수금 공식은 그대로 승계된다
   (문서 "종료 조건 → 일반모드 복귀" 절).

별% 공식 일반화
----------------
문서는 TQQQ/SOXL × 20/40분할 조합에 대해서만 구체적 수식을 제시한다:
  20분할 TQQQ (15 − 1.5T)% · 40분할 TQQQ (15 − 0.75T)%
  20분할 SOXL (20 − 2T)%   · 40분할 SOXL (20 − T)%
네 경우 모두 아래 단일 공식과 정확히 일치함을 확인하고, 이를 다른 분할수(예: 30)나
profit_target(예: KR 2x의 +10%)에도 적용할 수 있도록 일반화했다:
  star_pct(T) = profit_target × (1 − 2T / splits)

리버스모드 정수 상수 일반화
---------------------------
문서는 20분할·40분할에 대해서만 구체적 값을 제시한다 (등분 수 10/20, T 감쇠 0.9/0.95).
아래처럼 splits 하나로 두 값이 모두 정확히 재현되는 것을 확인하고 일반화했다:
  reverse_divisor (첫날 MOC 매도·이후 매도 등분 수) = splits // 2
  reverse_decay   (매도 시 T 감쇠 배수)              = 1 − 2/splits
쿼터매수 T 증가식(T + (splits−T)×0.25)은 문서에 이미 splits 파라미터화되어 있어 그대로 사용.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from lastofus.core.account import Account


# ---------------------------------------------------------------------------
# Star% formula (일반모드)
# ---------------------------------------------------------------------------

def star_pct_v4(rounds_done: float, splits: int, profit_target: float) -> float:
    """V4.0 별% 공식 — 별지점 = 평단 × (1 + star_pct).

    star_pct(T) = profit_target × (1 − 2T / splits)

    T=0 에서 +profit_target (평단보다 높은 곳도 매수/쿼터매도 대상), T=splits/2 에서 0%
    (평단과 동일), T=splits−1 에서 음수(평단 아래에서만 체결)로 선형 감소한다.
    전반전(T < splits/2)에는 이 값이 "매수점(별지점−0.01) + 평단" 이중 주문 중 하나로,
    후반전(T ≥ splits/2)에는 단독 매수 기준으로, 매도 시에는 항상 "쿼터매도" 트리거로 쓰인다.

    Parameters
    ----------
    rounds_done   : 현재 T값 (0 ~ splits 범위의 실수, 정수 아닐 수 있음)
    splits        : 분할수 (20/30/40)
    profit_target : 해당 종목의 익절 목표 비율 (TQQQ 0.15, SOXL 0.20 등)

    Returns
    -------
    별% (예: 0.15 = +15%, −0.06 = −6%)
    """
    return profit_target * (1.0 - 2.0 * rounds_done / splits)


# ---------------------------------------------------------------------------
# Main V4.0 strategy (일반모드 ⇄ 리버스모드 자동 전환)
# ---------------------------------------------------------------------------

def run_strategy_v4(
    df: pd.DataFrame,
    account: Account,
    profit_target: float,
) -> tuple[list[dict[str, Any]], list[float]]:
    """Run the V4.0 strategy (일반모드 ⇄ 리버스모드) over *df* using *account*.

    매 거래일마다 다음 순서로 처리한다:
      1. (일반모드) T가 소진(≥ splits−1)되어 있으면 리버스모드로 전환
      2. (일반모드) 1/4 쿼터매도(별지점 LOC) → 남은 수량 익절 지정가 매도(사이클 종료)
      3. (일반모드) 신규/전반전/후반전 매수 (1회매수금 = 잔금/(splits−T))
      4. (리버스모드) 무한매도(첫날 MOC, 이후 별지점 위 매도) → 쿼터매수(잔금/4)
      5. (리버스모드) 종료 조건 충족 시 다음날 일반모드로 복귀 플래그 설정

    Parameters
    ----------
    df            : OHLCV DataFrame (Open/High/Low/Close 컬럼 필요, High로 매도 체결 판정)
    account       : Account 인스턴스. account.splits 가 분할수(20/30/40)로 사용되고
                    account.rounds_done 이 T값 저장소로 재사용된다.
    profit_target : 익절 목표 비율 (TQQQ 0.15 / SOXL 0.20 — V3.0과 동일 값 재사용).
                    리버스모드 탈출 조건(−profit_target 선)에도 동일 값이 쓰인다.

    Returns
    -------
    trades      : 거래 이벤트 리스트. type은
                  BUY_NEW/BUY_STAR/BUY_AVG/BUY_STAR_FULL/QUARTER_SELL/SELL_TARGET
                  (일반모드) 또는 REVERSE_MOC_SELL/REVERSE_SELL/REVERSE_BUY (리버스모드).
    equity_list : df와 같은 길이의 일별 평가금(현금+보유주식가치) 리스트.
    """
    trades: list[dict[str, Any]] = []
    equity_list: list[float] = []

    splits = account.splits
    mode = "normal"
    close_history: list[float] = []
    reverse_first_day = False
    reverse_prev_holdings = 0.0

    # 리버스모드 매도 T 감쇠, 등분 수 — 20/40분할 공식(0.9/0.95, 10/20등분)을
    # splits/2 기준으로 일반화 (20→10등분·0.9, 40→20등분·0.95 모두 일치)
    reverse_decay = 1.0 - 2.0 / splits
    reverse_divisor = max(int(splits // 2), 1)

    for dt, row in df.iterrows():
        close_p: float = float(row["Close"])
        high_p: float = float(row["High"])

        if pd.isna(close_p) or close_p <= 0:
            equity_list.append(account.equity(0))
            continue

        date_str = str(dt.date()) if hasattr(dt, "date") else str(dt)

        # ------------------------------------------------------------------
        # 소진 체크 → 리버스모드 진입 (T > 분할수 − 1)
        # ------------------------------------------------------------------
        if mode == "normal" and account.shares > 0 and account.rounds_done >= splits - 1:
            mode = "reverse"
            reverse_first_day = True
            reverse_prev_holdings = account.shares

        if mode == "normal":
            # ----------------------------------------------------------------
            # SELL — 1/4 쿼터매도(별지점 LOC) + 나머지 익절 지정가 매도
            # ----------------------------------------------------------------
            if account.shares > 0 and account.avg_price > 0:
                T = account.rounds_done
                star = account.avg_price * (1.0 + star_pct_v4(T, splits, profit_target))

                if high_p >= star:
                    qty = account.shares * 0.25
                    proceeds = account.sell(star, qty)
                    if proceeds > 0:
                        account.rounds_done = T * 0.75
                        account.quarter_cut_count += 1
                        trades.append({
                            "date": date_str, "type": "QUARTER_SELL",
                            "price": star, "qty": proceeds / star,
                            "proceeds": proceeds, "cycle": account.cycle_count,
                        })

                if account.shares > 0:
                    profit_price = account.avg_price * (1.0 + profit_target)
                    if high_p >= profit_price:
                        T_before = account.rounds_done
                        proceeds = account.sell(profit_price, account.shares)
                        if proceeds > 0:
                            # 사이클 종료 — T는 0이 아닌 T×0.25로 이월
                            if account.reinvest_ratio > 0 and account.cash > account.principal:
                                profit = account.cash - account.principal
                                reinvest_amount = profit * account.reinvest_ratio
                                withdraw_amount = profit * (1.0 - account.reinvest_ratio)
                                account.cash -= withdraw_amount
                                account.reserved_cash += withdraw_amount
                                account.principal += reinvest_amount
                            account.shares = 0.0
                            account.avg_price = 0.0
                            account.rounds_done = T_before * 0.25
                            account.cycle_count += 1
                            trades.append({
                                "date": date_str, "type": "SELL_TARGET",
                                "price": profit_price, "qty": proceeds / profit_price,
                                "proceeds": proceeds, "cycle": account.cycle_count,
                            })

            # ----------------------------------------------------------------
            # BUY — 1회매수금 = 잔금 / (분할수 − T)
            # ----------------------------------------------------------------
            T = account.rounds_done
            remaining_slots = max(splits - T, 1e-6)
            unit = account.cash / remaining_slots if account.cash > 0 else 0.0

            if account.shares == 0:
                spent = account.buy(close_p, unit)
                if spent > 0:
                    account.rounds_done += 1.0
                    trades.append({
                        "date": date_str, "type": "BUY_NEW",
                        "price": close_p, "qty": spent / close_p,
                        "spent": spent, "cycle": account.cycle_count,
                    })

            elif T < splits / 2.0:
                # 전반전 — 별지점(0.5) + 평단(0.5) 이중 LOC
                half = unit / 2.0
                star_buy = account.avg_price * (1.0 + star_pct_v4(T, splits, profit_target)) - 0.01

                if close_p <= star_buy:
                    spent = account.buy(close_p, half)
                    if spent > 0:
                        account.rounds_done += 0.5
                        trades.append({
                            "date": date_str, "type": "BUY_STAR",
                            "price": close_p, "qty": spent / close_p,
                            "spent": spent, "cycle": account.cycle_count,
                        })

                if close_p <= account.avg_price:
                    spent = account.buy(close_p, half)
                    if spent > 0:
                        account.rounds_done += 0.5
                        trades.append({
                            "date": date_str, "type": "BUY_AVG",
                            "price": close_p, "qty": spent / close_p,
                            "spent": spent, "cycle": account.cycle_count,
                        })

            else:
                # 후반전 — 별지점(평단 이하) 단일 LOC
                star_buy = account.avg_price * (1.0 + star_pct_v4(T, splits, profit_target)) - 0.01
                if close_p <= star_buy:
                    spent = account.buy(close_p, unit)
                    if spent > 0:
                        account.rounds_done += 1.0
                        trades.append({
                            "date": date_str, "type": "BUY_STAR_FULL",
                            "price": close_p, "qty": spent / close_p,
                            "spent": spent, "cycle": account.cycle_count,
                        })

        else:
            # ================================================================
            # 리버스모드 — 무한매도 + 쿼터매수
            # ================================================================
            star_rev = (
                sum(close_history[-5:]) / len(close_history[-5:])
                if close_history else close_p
            )

            if reverse_first_day:
                # 첫날 — MOC 무조건 매도 (splits/2 등분, 내림)
                sell_qty = float(int(account.shares / reverse_divisor))
                if sell_qty > 0:
                    proceeds = account.sell(close_p, sell_qty)
                    if proceeds > 0:
                        account.rounds_done *= reverse_decay
                        trades.append({
                            "date": date_str, "type": "REVERSE_MOC_SELL",
                            "price": close_p, "qty": sell_qty,
                            "proceeds": proceeds, "cycle": account.cycle_count,
                        })
                reverse_prev_holdings = account.shares
                reverse_first_day = False
            else:
                # 둘째날 이후 — 별지점 위에서 매도 (직전 보유수의 등분)
                if account.shares > 0 and close_p >= star_rev:
                    sell_qty = min(float(int(reverse_prev_holdings / reverse_divisor)), account.shares)
                    if sell_qty > 0:
                        proceeds = account.sell(star_rev, sell_qty)
                        if proceeds > 0:
                            account.rounds_done *= reverse_decay
                            trades.append({
                                "date": date_str, "type": "REVERSE_SELL",
                                "price": star_rev, "qty": sell_qty,
                                "proceeds": proceeds, "cycle": account.cycle_count,
                            })
                reverse_prev_holdings = account.shares

                # 쿼터매수 — 잔금/4를 별지점 아래에서 LOC 매수
                if account.cash > 0 and close_p <= star_rev:
                    buy_amount = account.cash / 4.0
                    spent = account.buy(close_p, buy_amount)
                    if spent > 0:
                        account.rounds_done += (splits - account.rounds_done) * 0.25
                        trades.append({
                            "date": date_str, "type": "REVERSE_BUY",
                            "price": close_p, "qty": spent / close_p,
                            "spent": spent, "cycle": account.cycle_count,
                        })

            # 종료 조건 — 종가가 평단 대비 −profit_target% 선을 넘어서면
            # 다음 거래일부터 일반모드 복귀 (T·1회매수금 공식은 그대로 승계)
            if account.avg_price > 0:
                recovery_line = account.avg_price * (1.0 - profit_target)
                if close_p > recovery_line:
                    mode = "normal"

        close_history.append(close_p)
        if len(close_history) > 5:
            close_history.pop(0)

        equity_list.append(account.equity(close_p))

    return trades, equity_list


# ---------------------------------------------------------------------------
# Benchmarks (re-export for convenience)
# ---------------------------------------------------------------------------

from lastofus.strategy.infinite_v22 import run_bah, run_dca  # noqa: E402
