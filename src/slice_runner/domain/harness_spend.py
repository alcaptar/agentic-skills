from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessSpend:
    cost_usd: float = 0.0
    turns: int = 0
    duration_ms: int = 0
    calls: int = 0

    @classmethod
    def nothing(cls) -> HarnessSpend:
        return cls()

    @classmethod
    def of_a_call(cls, *, cost_usd: float, turns: int, duration_ms: int) -> HarnessSpend:
        return cls(cost_usd=cost_usd, turns=turns, duration_ms=duration_ms, calls=1)

    @classmethod
    def summing(cls, spends: Iterable[HarnessSpend]) -> HarnessSpend:
        return reduce(cls.plus, spends, cls.nothing())

    @property
    def measured(self) -> bool:
        return self.calls > 0

    def plus(self, other: HarnessSpend) -> HarnessSpend:
        return HarnessSpend(
            cost_usd=self.cost_usd + other.cost_usd,
            turns=self.turns + other.turns,
            duration_ms=self.duration_ms + other.duration_ms,
            calls=self.calls + other.calls,
        )
