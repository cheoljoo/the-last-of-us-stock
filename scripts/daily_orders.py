#!/usr/bin/env python
"""Compute and display today's LOC buy and limit sell orders.

Reads state/<TICKER>_state.json for each ticker.
Fetches the latest close price from yfinance.
Prints a human-readable action list.

Usage:
    uv run python scripts/daily_orders.py [--state STATE_DIR] [--tickers TQQQ SPXL]

State JSON format:
    {
        "ticker":       "TQQQ",
        "shares":       12.5,
        "avg_price":    45.23,
        "rounds_done":  8.0,
        "cycle_count":  3,
        "cash":         7500.0,
        "principal":    10000.0,
        "splits":       40
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from lastofus.config import TICKER_CONFIG, DEFAULT_PRINCIPAL_KRW, DEFAULT_PRINCIPAL_USD
from lastofus.data.loader import get_latest_price

STATE_DIR = Path(__file__).parents[1] / "state"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="오늘의 주문 목록 출력")
    parser.add_argument(
        "--state",
        type=str,
        default=None,
        help="State directory (default: state/)",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        metavar="TICKER",
        default=None,
        help="Tickers to show (default: all configured)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Interactively update state files after displaying orders",
    )
    return parser.parse_args()


def load_state(state_dir: Path, ticker: str) -> dict | None:
    fname = state_dir / f"{ticker.replace('.', '_')}_state.json"
    if not fname.exists():
        return None
    with open(fname, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_state(state_dir: Path, ticker: str, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    fname = state_dir / f"{ticker.replace('.', '_')}_state.json"
    with open(fname, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    print(f"  State saved → {fname}")


def default_state(ticker: str) -> dict:
    cfg = TICKER_CONFIG.get(ticker, {})
    market = cfg.get("market", "US")
    principal = DEFAULT_PRINCIPAL_KRW if market == "KR" else DEFAULT_PRINCIPAL_USD
    return {
        "ticker":      ticker,
        "shares":      0.0,
        "avg_price":   0.0,
        "rounds_done": 0.0,
        "cycle_count": 0,
        "quarter_cut_count": 0,
        "cash":        principal,
        "principal":   principal,
        "splits":      cfg.get("splits", 40),
    }


def compute_orders(state: dict, current_price: float) -> dict:
    """Compute what orders to place given account state and current price."""
    ticker       = state["ticker"]
    cfg          = TICKER_CONFIG.get(ticker, {})
    profit_target = cfg.get("profit_target", 0.10)
    splits       = state.get("splits", 40)
    principal    = state.get("principal", DEFAULT_PRINCIPAL_USD)
    shares       = float(state.get("shares", 0.0))
    avg_price    = float(state.get("avg_price", 0.0))
    rounds_done  = float(state.get("rounds_done", 0.0))
    cash         = float(state.get("cash", principal))
    unit_amount  = principal / splits
    progress     = rounds_done / splits

    orders = []
    notes  = []

    # ---- Sell check -------------------------------------------------------
    if shares > 0 and avg_price > 0:
        sell_limit = avg_price * (1.0 + profit_target)
        if current_price >= sell_limit:
            orders.append({
                "action":    "SELL (목표 달성!)",
                "type":      "지정가 매도",
                "price":     sell_limit,
                "qty":       shares,
                "amount":    shares * sell_limit,
                "urgent":    True,
            })
            notes.append(f"  ★ 오늘 목표가({sell_limit:.4f}) 달성! 전량 매도 주문 필요")
            return {"orders": orders, "notes": notes, "action_required": True}
        else:
            pct_to_target = (sell_limit - current_price) / current_price * 100
            notes.append(
                f"  매도 목표가: {sell_limit:.4f} (현재 {pct_to_target:.1f}% 부족)"
            )

    # ---- Quarter cut check ------------------------------------------------
    if rounds_done >= splits and shares > 0:
        sell_qty = shares * 0.25
        orders.append({
            "action":    "QUARTER CUT (쿼터컷)",
            "type":      "시장가 매도",
            "price":     current_price,
            "qty":       sell_qty,
            "amount":    sell_qty * current_price,
            "urgent":    True,
        })
        notes.append(f"  ★ 40분할 소진! 보유수량 25% 쿼터컷 매도 필요")
        return {"orders": orders, "notes": notes, "action_required": True}

    # ---- Buy logic --------------------------------------------------------
    if shares == 0:
        # New cycle
        buy_amount = min(unit_amount, cash)
        orders.append({
            "action":    "BUY (신규 진입)",
            "type":      "LOC 시장가",
            "price":     current_price,
            "qty":       buy_amount / current_price,
            "amount":    buy_amount,
            "urgent":    False,
        })
        notes.append("  신규 사이클 시작: 1유닛 매수")

    elif progress <= 0.5:
        # 전반전
        half = unit_amount / 2.0
        loc1_price = avg_price
        loc2_price = avg_price * 1.05

        if current_price <= avg_price:
            # Both fire
            orders.append({
                "action":    "BUY LOC1 + LOC2 (전반전, 이중 매수)",
                "type":      f"LOC 지정가 ≤ {avg_price:.4f}",
                "price":     current_price,
                "qty":       (half * 2) / current_price,
                "amount":    half * 2,
                "urgent":    False,
            })
            notes.append(f"  현재가({current_price:.4f}) ≤ 평단가({avg_price:.4f}): LOC1+LOC2 모두 체결")
        elif current_price <= avg_price * 1.05:
            # Only LOC2
            orders.append({
                "action":    "BUY LOC2 (전반전, 0.5유닛)",
                "type":      f"LOC 지정가 ≤ {loc2_price:.4f}",
                "price":     current_price,
                "qty":       half / current_price,
                "amount":    half,
                "urgent":    False,
            })
            notes.append(f"  평단가({avg_price:.4f}) < 현재가({current_price:.4f}) ≤ 평단가×1.05({loc2_price:.4f}): LOC2만 체결")
        else:
            notes.append(
                f"  현재가({current_price:.4f}) > 평단가×1.05({loc2_price:.4f}): 오늘 매수 없음"
            )

    else:
        # 후반전
        if current_price <= avg_price:
            orders.append({
                "action":    "BUY (후반전, 1유닛)",
                "type":      f"LOC 지정가 ≤ {avg_price:.4f}",
                "price":     current_price,
                "qty":       unit_amount / current_price,
                "amount":    unit_amount,
                "urgent":    False,
            })
            notes.append(f"  현재가({current_price:.4f}) ≤ 평단가({avg_price:.4f}): 1유닛 매수")
        else:
            notes.append(
                f"  후반전: 현재가({current_price:.4f}) > 평단가({avg_price:.4f}): 오늘 매수 없음"
            )

    return {
        "orders": orders,
        "notes":  notes,
        "action_required": len(orders) > 0,
    }


def print_ticker_summary(ticker: str, state: dict | None, current_price: float | None) -> None:
    cfg  = TICKER_CONFIG.get(ticker, {})
    name = cfg.get("name", ticker)
    market = cfg.get("market", "US")
    currency = "KRW" if market == "KR" else "USD"

    print(f"\n{'='*60}")
    print(f"  {ticker}  —  {name}")
    print(f"{'='*60}")

    if current_price is None:
        print(f"  ⚠  현재가 조회 실패")
    else:
        print(f"  현재가: {current_price:,.4f} {currency}")

    if state is None:
        print(f"  상태 파일 없음 — 기본값(신규 시작) 사용")
        state = default_state(ticker)

    shares      = float(state.get("shares", 0.0))
    avg_price   = float(state.get("avg_price", 0.0))
    rounds_done = float(state.get("rounds_done", 0.0))
    cash        = float(state.get("cash", state.get("principal", 0)))
    principal   = float(state.get("principal", 0))
    splits      = int(state.get("splits", 40))
    cycles      = int(state.get("cycle_count", 0))
    qcuts       = int(state.get("quarter_cut_count", 0))
    progress    = rounds_done / splits * 100

    equity = cash + shares * (current_price or avg_price or 0)
    total_ret = (equity - principal) / principal * 100 if principal > 0 else 0

    print(f"  보유수량:   {shares:,.4f}주")
    print(f"  평균단가:   {avg_price:,.4f} {currency}")
    print(f"  보유현금:   {cash:,.0f} {currency}")
    print(f"  총평가금액: {equity:,.0f} {currency}  (수익률 {total_ret:+.1f}%)")
    print(f"  진행도:     {rounds_done:.1f}/{splits} ({progress:.1f}%)")
    print(f"  사이클 #:   {cycles}  |  쿼터컷 #: {qcuts}")

    if current_price is None:
        print("  주문 계산 불가 (현재가 없음)")
        return

    result = compute_orders(state, current_price)

    if not result["orders"]:
        print(f"\n  오늘 주문: 없음")
    else:
        print(f"\n  오늘 주문:")
        for o in result["orders"]:
            urgent = " ★★★" if o.get("urgent") else ""
            print(f"    [{o['action']}]{urgent}")
            print(f"      유형:   {o['type']}")
            print(f"      수량:   {o['qty']:,.4f}주")
            print(f"      금액:   {o['amount']:,.0f} {currency}")

    for note in result["notes"]:
        print(note)


def main() -> int:
    args = parse_args()

    state_dir = Path(args.state) if args.state else STATE_DIR
    tickers   = args.tickers if args.tickers else list(TICKER_CONFIG.keys())

    today = date.today()
    print(f"\n라오어 무한매수법 V2.2 — 오늘의 주문 목록")
    print(f"날짜: {today}  |  총 {len(tickers)}개 티커")

    action_needed = []

    for ticker in tickers:
        state = load_state(state_dir, ticker)
        print(f"\n  {ticker}: 현재가 조회 중...", end=" ", flush=True)
        price = get_latest_price(ticker)
        if price is None:
            print("실패")
        else:
            print(f"{price:,.4f}")

        print_ticker_summary(ticker, state, price)

        if price is not None:
            s = state if state is not None else default_state(ticker)
            result = compute_orders(s, price)
            if result["action_required"]:
                action_needed.append(ticker)

    # Summary
    print(f"\n{'='*60}")
    print(f"  요약: 오늘 주문이 필요한 티커")
    print(f"{'='*60}")
    if action_needed:
        for t in action_needed:
            print(f"  ★ {t}")
    else:
        print("  오늘 주문 없음")

    # Interactive update
    if args.update and action_needed:
        print(f"\n상태 파일 업데이트를 원하시면 티커별로 값을 입력하세요.")
        print("(Enter 키만 누르면 건너뜁니다)")
        for ticker in tickers:
            state = load_state(state_dir, ticker)
            if state is None:
                state = default_state(ticker)

            print(f"\n  {ticker} 상태 업데이트:")
            try:
                new_shares = input(f"    보유수량 [{state.get('shares', 0):.4f}]: ").strip()
                if new_shares:
                    state["shares"] = float(new_shares)

                new_avg = input(f"    평균단가 [{state.get('avg_price', 0):.4f}]: ").strip()
                if new_avg:
                    state["avg_price"] = float(new_avg)

                new_cash = input(f"    보유현금 [{state.get('cash', 0):.0f}]: ").strip()
                if new_cash:
                    state["cash"] = float(new_cash)

                new_rounds = input(f"    rounds_done [{state.get('rounds_done', 0):.1f}]: ").strip()
                if new_rounds:
                    state["rounds_done"] = float(new_rounds)

                save_choice = input("    저장? (y/N): ").strip().lower()
                if save_choice == "y":
                    save_state(state_dir, ticker, state)
            except (EOFError, KeyboardInterrupt):
                print("\n  업데이트 취소됨")
                break

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
