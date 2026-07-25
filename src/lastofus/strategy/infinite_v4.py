"""무한매수법 V4.0 strategy implementation (일반모드 + 리버스모드 통합).

출처: https://quantstack.app/infinite/v4-0-normal/, .../v4-0-reverse/
(quantstack.app 비공식 정리 사이트. 원 방법론 저작권자: 라오어 —
네이버 카페 "무한매수법 & 밸류리밸런싱 공부모임")

V3.0 대비 핵심 변화:
  - T 계산 단순화: 매수누적액 나눗셈이 아닌 회차 가산 방식
  - 1회매수금 = 잔금 / (분할수 − T)  → 매일 미세하게 변동 (V2.2/V3.0은 고정 principal/splits)
  - 매도: 보유수량의 1/4은 별지점에서 LOC 매도(쿼터매도, T×0.75로 감소),
          나머지는 고정 익절가(TQQQ +15% / SOXL +20%)에서 지정가 매도(사이클 종료).
          사이클 종료 시 T는 0으로 리셋되지 않고 T×0.25로 이월된다.
  - 소진(T > 분할수−1) 시 쿼터컷이 아닌 리버스모드(무한매도 + 쿼터매수) 진입.
    리버스모드는 평단 대비 −15%/−20% 선을 종가가 넘어서면 다음날 일반모드로 복귀.

별% 공식은 V3.0과 동일한 형태를 20/30/40분할로 일반화한 것이다:
  star_pct(T) = profit_target × (1 − 2T / splits)
  (TQQQ 20분할 (15−1.5T)%, 40분할 (15−0.75T)%, SOXL 20분할 (20−2T)%, 40분할 (20−T)%
   과 각각 일치함을 확인함)
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from lastofus.core.account import Account


# ---------------------------------------------------------------------------
# Star% formula (일반모드)
# ---------------------------------------------------------------------------

def star_pct_v4(rounds_done: float, splits: int, profit_target: float) -> float:
    """V4.0 별% = target% × (1 − 2T/splits). T=0→+target%, T=splits/2→0%."""
    return profit_target * (1.0 - 2.0 * rounds_done / splits)


# ---------------------------------------------------------------------------
# Main V4.0 strategy (일반모드 ⇄ 리버스모드 자동 전환)
# ---------------------------------------------------------------------------

def run_strategy_v4(
    df: pd.DataFrame,
    account: Account,
    profit_target: float,
) -> tuple[list[dict[str, Any]], list[float]]:
    """Run the V4.0 strategy over *df* using *account*.

    account.splits 가 분할수(20/30/40)로 사용된다.
    Reverse submode 진입/복귀는 자동으로 처리되며 결과 trades에
    "REVERSE_*" type으로 표기된다.
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
