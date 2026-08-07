from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.harness_spend import HarnessSpend

if TYPE_CHECKING:
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class Run:
    step: Step
    control_retries: int = 0
    verify_retries: int = 0
    ci_retries: int = 0
    indeterminate_ticks: int = 0
    verify_discards: int = 0
    spend: HarnessSpend = field(default_factory=HarnessSpend.nothing)

    @property
    def implement_retries(self) -> int:
        return self.control_retries + self.verify_retries + self.ci_retries
