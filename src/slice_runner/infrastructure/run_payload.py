from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field

from slice_runner.domain.run import Run
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel

Spent = Annotated[int, Field(strict=True, ge=0)]


class RunPayload(ContractModel):
    step: Step
    control_retries: Spent = 0
    verify_retries: Spent = 0
    ci_retries: Spent = 0
    indeterminate_ticks: Spent = 0
    verify_discards: Spent = 0

    @classmethod
    def from_domain(cls, run: Run) -> Self:
        return cls(
            step=run.step,
            control_retries=run.control_retries,
            verify_retries=run.verify_retries,
            ci_retries=run.ci_retries,
            indeterminate_ticks=run.indeterminate_ticks,
            verify_discards=run.verify_discards,
        )

    def to_domain(self) -> Run:
        return Run(
            step=self.step,
            control_retries=self.control_retries,
            verify_retries=self.verify_retries,
            ci_retries=self.ci_retries,
            indeterminate_ticks=self.indeterminate_ticks,
            verify_discards=self.verify_discards,
        )
