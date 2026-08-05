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
