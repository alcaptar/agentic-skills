from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.run import Run
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend


class RunMother:
    @staticmethod
    def implementing() -> Run:
        return Run(step=Step.IMPLEMENT)

    @staticmethod
    def judging_after_spending(spend: HarnessSpend) -> Run:
        return Run(step=Step.VERIFY, spend=spend)

    @staticmethod
    def running_the_controls() -> Run:
        return Run(step=Step.RUN_CONTROLS)

    @staticmethod
    def judging() -> Run:
        return Run(step=Step.VERIFY)

    @staticmethod
    def about_to_ask_the_ci() -> Run:
        return Run(step=Step.AWAIT_CI)

    @staticmethod
    def awaiting_ci() -> Run:
        return Run(step=Step.AWAIT_CI, control_retries=1, indeterminate_ticks=2)

    @staticmethod
    def with_the_only_ci_retry_already_spent() -> Run:
        return Run(step=Step.AWAIT_CI, ci_retries=1)

    @staticmethod
    def awaiting_merge() -> Run:
        return Run(step=Step.AWAIT_MERGE)

    @staticmethod
    def awaiting_alignment_after_a_published_correction(correction: str) -> Run:
        return Run(step=Step.UNDERSTAND, corrected=correction)

    @staticmethod
    def that_went_back_for_every_reason() -> Run:
        return Run(
            step=Step.AWAIT_MERGE,
            control_retries=1,
            hygiene_retries=5,
            verify_retries=2,
            correction_retries=6,
            ci_retries=3,
            verify_discards=4,
        )
