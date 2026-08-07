from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field

from slice_runner.domain.exceptions import UnreadableRunError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.run import Run
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.spend_payload import SpendPayload

Spent = Annotated[int, Field(strict=True, ge=0)]


class RunPayload(ContractModel):
    step: Step
    control_retries: Spent = 0
    hygiene_retries: Spent = 0
    verify_retries: Spent = 0
    ci_retries: Spent = 0
    indeterminate_ticks: Spent = 0
    verify_discards: Spent = 0
    spend: SpendPayload | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "the execution state block is not one this program can read", UnreadableRunError)

    @classmethod
    def from_domain(cls, run: Run) -> Self:
        return cls(
            step=run.step,
            control_retries=run.control_retries,
            hygiene_retries=run.hygiene_retries,
            verify_retries=run.verify_retries,
            ci_retries=run.ci_retries,
            indeterminate_ticks=run.indeterminate_ticks,
            verify_discards=run.verify_discards,
            spend=SpendPayload.from_domain(run.spend) if run.spend.measured else None,
        )

    def to_domain(self) -> Run:
        return Run(
            step=self.step,
            control_retries=self.control_retries,
            hygiene_retries=self.hygiene_retries,
            verify_retries=self.verify_retries,
            ci_retries=self.ci_retries,
            indeterminate_ticks=self.indeterminate_ticks,
            verify_discards=self.verify_discards,
            spend=self.spend.to_domain() if self.spend is not None else HarnessSpend.nothing(),
        )
