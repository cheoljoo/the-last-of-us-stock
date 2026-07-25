"""Account state for 라오어 무한매수법 (V2.2 / V3.0)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Account:
    """Tracks a single ticker's position and cash."""

    principal: float
    splits: int = 40
    reinvest_ratio: float = 0.0    # 수익의 몇 %를 다음 사이클 원금에 재투자 (0~1)

    cash: float = 0.0
    shares: float = 0.0
    avg_price: float = 0.0
    rounds_done: float = 0.0
    cycle_count: int = 0
    quarter_cut_count: int = 0
    total_realized_pnl: float = 0.0
    reserved_cash: float = 0.0     # 인출된 누적 수익 (reinvest_ratio < 1 시)

    def __post_init__(self) -> None:
        if self.cash == 0.0:
            self.cash = self.principal

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def unit_amount(self) -> float:
        """Amount spent per single 'round' (principal / splits)."""
        return self.principal / self.splits

    @property
    def progress(self) -> float:
        """Fraction of rounds completed this cycle (0.0 – 1.0+)."""
        return self.rounds_done / self.splits

    # ------------------------------------------------------------------
    # Trading operations
    # ------------------------------------------------------------------

    def buy(self, price: float, amount: float) -> float:
        """Buy as much as *amount* allows at *price*. Returns actual spend."""
        if price <= 0:
            return 0.0
        actual_amount = min(amount, self.cash)
        if actual_amount < price * 1e-6:
            return 0.0

        qty = actual_amount / price
        total_cost = self.shares * self.avg_price + actual_amount
        self.shares += qty
        self.avg_price = total_cost / self.shares
        self.cash -= actual_amount
        return actual_amount

    def sell(self, price: float, qty: float) -> float:
        """Sell *qty* shares at *price*. Returns proceeds."""
        if price <= 0 or qty <= 0:
            return 0.0
        actual_qty = min(qty, self.shares)
        if actual_qty <= 1e-9:
            return 0.0

        proceeds = price * actual_qty
        pnl = (price - self.avg_price) * actual_qty
        self.total_realized_pnl += pnl
        self.cash += proceeds
        self.shares -= actual_qty

        if self.shares < 1e-9:
            self.shares = 0.0
            self.avg_price = 0.0

        return proceeds

    def reset_cycle(self) -> None:
        """Called after a full-profit sell. Applies partial compounding if set."""
        # Apply compounding only on profitable cycles
        if self.reinvest_ratio > 0 and self.cash > self.principal:
            profit = self.cash - self.principal
            reinvest_amount = profit * self.reinvest_ratio
            withdraw_amount = profit * (1.0 - self.reinvest_ratio)
            # Move withdrawn portion out of active cash
            self.cash -= withdraw_amount
            self.reserved_cash += withdraw_amount
            # Grow principal for next cycle
            self.principal += reinvest_amount

        self.shares = 0.0
        self.avg_price = 0.0
        self.rounds_done = 0.0
        self.cycle_count += 1

    # ------------------------------------------------------------------
    # Valuation helpers
    # ------------------------------------------------------------------

    def equity(self, price: float) -> float:
        """Total account value at *price* (active cash only)."""
        return self.cash + self.shares * price

    def total_value(self, price: float) -> float:
        """Includes reserved_cash (non-reinvested withdrawn profits)."""
        return self.cash + self.shares * price + self.reserved_cash

    def unrealized_pct(self, price: float) -> float:
        """Unrealized return on current position (0 if no position)."""
        if self.avg_price == 0 or self.shares == 0:
            return 0.0
        return (price - self.avg_price) / self.avg_price

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "principal": self.principal,
            "splits": self.splits,
            "reinvest_ratio": self.reinvest_ratio,
            "cash": self.cash,
            "shares": self.shares,
            "avg_price": self.avg_price,
            "rounds_done": self.rounds_done,
            "cycle_count": self.cycle_count,
            "quarter_cut_count": self.quarter_cut_count,
            "total_realized_pnl": self.total_realized_pnl,
            "reserved_cash": self.reserved_cash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Account":
        return cls(
            principal=d["principal"],
            splits=d.get("splits", 40),
            reinvest_ratio=d.get("reinvest_ratio", 0.0),
            cash=d.get("cash", d["principal"]),
            shares=d.get("shares", 0.0),
            avg_price=d.get("avg_price", 0.0),
            rounds_done=d.get("rounds_done", 0.0),
            cycle_count=d.get("cycle_count", 0),
            quarter_cut_count=d.get("quarter_cut_count", 0),
            total_realized_pnl=d.get("total_realized_pnl", 0.0),
            reserved_cash=d.get("reserved_cash", 0.0),
        )
