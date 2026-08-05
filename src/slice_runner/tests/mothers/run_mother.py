from __future__ import annotations

from slice_runner.domain.run import Run
from slice_runner.domain.step import Step


class RunMother:
    @staticmethod
    def implementing() -> Run:
        return Run(step=Step.IMPLEMENT)

    @staticmethod
    def awaiting_ci() -> Run:
        return Run(step=Step.AWAIT_CI, control_retries=1, indeterminate_ticks=2)

    @staticmethod
    def awaiting_merge() -> Run:
        return Run(step=Step.AWAIT_MERGE)

    @staticmethod
    def that_went_back_for_every_reason() -> Run:
        return Run(step=Step.AWAIT_MERGE, control_retries=1, verify_retries=2, ci_retries=3, verify_discards=4)
