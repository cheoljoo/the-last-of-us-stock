"""Account state for 라오어 무한매수법 V2.2."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Account:
    """Tracks a single ticker's position and cash."""

    principal: float
    splits: int = 40
    cash: float = 0.0
    shares: float = 0.0
    avg_price: float = 0.0
    rounds_done: float = 0.0
    cycle_count: int = 0
    quarter_cut_count: int = 0
    total_realized_pnl: float = 0.0

    def __post_init__(self) -> None:
        # Cash defaults to principal when not provided
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
        """Called after a full-profit sell. Cash is kept as-is."""
        self.shares = 0.0
        self.avg_price = 0.0
        self.rounds_done = 0.0
        self.cycle_count += 1

    # ------------------------------------------------------------------
    # Valuation helpers
    # ------------------------------------------------------------------

    def equity(self, price: float) -> float:
        """Total account value at *price*."""
        return self.cash + self.shares * price

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
            "cash": self.cash,
            "shares": self.shares,
            "avg_price": self.avg_price,
            "rounds_done": self.rounds_done,
            "cycle_count": self.cycle_count,
            "quarter_cut_count": self.quarter_cut_count,
            "total_realized_pnl": self.total_realized_pnl,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Account":
        return cls(
            principal=d["principal"],
            splits=d.get("splits", 40),
            cash=d.get("cash", d["principal"]),
            shares=d.get("shares", 0.0),
            avg_price=d.get("avg_price", 0.0),
            rounds_done=d.get("rounds_done", 0.0),
            cycle_count=d.get("cycle_count", 0),
            quarter_cut_count=d.get("quarter_cut_count", 0),
            total_realized_pnl=d.get("total_realized_pnl", 0.0),
        )
