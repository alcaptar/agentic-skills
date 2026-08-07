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
    models: tuple[str, ...] = ()
    cache_read_tokens: int = 0

    @classmethod
    def nothing(cls) -> HarnessSpend:
        return cls()

    @classmethod
    def of_a_call(
        cls, *, cost_usd: float, turns: int, duration_ms: int, models: tuple[str, ...] = (), cache_read_tokens: int = 0
    ) -> HarnessSpend:
        return cls(
            cost_usd=cost_usd,
            turns=turns,
            duration_ms=duration_ms,
            calls=1,
            models=tuple(sorted(set(models))),
            cache_read_tokens=cache_read_tokens,
        )

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
            models=tuple(sorted(set(self.models) | set(other.models))),
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
        )
