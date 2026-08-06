from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend


class SpendPayload(ContractModel):
    cost_usd: float
    turns: int
    duration_ms: int
    calls: int

    @classmethod
    def from_domain(cls, spend: HarnessSpend) -> Self:
        return cls(cost_usd=spend.cost_usd, turns=spend.turns, duration_ms=spend.duration_ms, calls=spend.calls)
