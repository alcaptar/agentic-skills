from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from slice_runner.domain.alignment_stage import AlignmentStage
from slice_runner.domain.exceptions import OrderRefusedError
from slice_runner.domain.order import Order
from slice_runner.domain.slice_queue import SliceQueue

if TYPE_CHECKING:
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class CorrectUnderstandingParams:
    repo: str
    subissue: SubIssue
    correction: str


@dataclass(frozen=True, kw_only=True, slots=True)
class CorrectUnderstandingResult:
    subissue: SubIssue


class CorrectUnderstanding:
    def __init__(self, *, repository: RunRepository) -> None:
        self._repository = repository

    def execute(self, params: CorrectUnderstandingParams) -> CorrectUnderstandingResult:
        subissue = params.subissue
        if subissue.run is None or not SliceQueue.awaiting_a_correction_to_be_replaced(subissue):
            raise OrderRefusedError(
                f"subissue #{subissue.number} is not waiting for the alignment, so it has no understanding to correct"
            )

        run = replace(subissue.run, corrected=params.correction, alignment=AlignmentStage.DRAFT)
        self._repository.write_run(repo=params.repo, issue=subissue.number, run=run)
        self._repository.mark_order(repo=params.repo, issue=subissue.number, order=Order.REVIEW, text=params.correction)

        return CorrectUnderstandingResult(subissue=replace(subissue, run=run))
