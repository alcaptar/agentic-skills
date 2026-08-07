from __future__ import annotations

from typing import Self

from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.infrastructure.contract_model import ContractModel


class SpendPayload(ContractModel):
    cost_usd: float
    turns: int
    duration_ms: int
    calls: int

    @classmethod
    def from_domain(cls, spend: HarnessSpend) -> Self:
        return cls(cost_usd=spend.cost_usd, turns=spend.turns, duration_ms=spend.duration_ms, calls=spend.calls)

    def to_domain(self) -> HarnessSpend:
        return HarnessSpend(cost_usd=self.cost_usd, turns=self.turns, duration_ms=self.duration_ms, calls=self.calls)
