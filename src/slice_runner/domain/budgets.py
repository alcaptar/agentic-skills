from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend


@dataclass(frozen=True, kw_only=True, slots=True)
class Budgets:
    control_retries: int = 2
    hygiene_retries: int = 2
    verify_retries: int = 2
    ci_retries: int = 1
    indeterminate_ticks: int = 3
    seconds_between_ticks: int = 30
    total_wait_seconds: int = 1800
    process_timeout_seconds: int = 3600
    slice_cost_usd: float = 50.0

    def wait_exhausted(self, waited_seconds: int) -> bool:
        return waited_seconds >= self.total_wait_seconds

    def exhausted(self, total: HarnessSpend) -> bool:
        return total.cost_usd >= self.slice_cost_usd

    def cost_exhausted(self, *, call: HarnessSpend | None, total: HarnessSpend) -> bool:
        if call is None or not call.measured:
            return True

        return self.exhausted(total)
