from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from slice_runner.domain.harness_spend import HarnessSpend

if TYPE_CHECKING:
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class Run:
    step: Step
    corrected: str = ""
    understanding_pending: bool = False
    control_retries: int = 0
    hygiene_retries: int = 0
    verify_retries: int = 0
    correction_retries: int = 0
    ci_retries: int = 0
    indeterminate_ticks: int = 0
    verify_discards: int = 0
    understand_discards: int = 0
    implement_discards: int = 0
    control_rounds_logged: int = 0
    last_reviewed_id: int = 0
    requested_changes: tuple[str, ...] = ()
    spend: HarnessSpend = field(default_factory=HarnessSpend.nothing)

    @property
    def correcting_review(self) -> bool:
        return bool(self.requested_changes)

    @property
    def implement_retries(self) -> int:
        return (
            self.control_retries
            + self.hygiene_retries
            + self.verify_retries
            + self.correction_retries
            + self.ci_retries
        )
