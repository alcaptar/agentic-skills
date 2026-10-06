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
class AgreeUnderstandingParams:
    repo: str
    subissue: SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class AgreeUnderstandingResult:
    subissue: SubIssue


class AgreeUnderstanding:
    def __init__(self, *, repository: RunRepository) -> None:
        self._repository = repository

    def execute(self, params: AgreeUnderstandingParams) -> AgreeUnderstandingResult:
        subissue = params.subissue
        if subissue.run is None or not SliceQueue.awaiting_alignment(subissue):
            raise OrderRefusedError(
                f"subissue #{subissue.number} is not waiting for the alignment, so it has nothing to agree"
            )

        run = replace(subissue.run, alignment=AlignmentStage.AGREED)
        self._repository.write_run(repo=params.repo, issue=subissue.number, run=run)
        self._repository.mark_order(repo=params.repo, issue=subissue.number, order=Order.GO, text="")

        return AgreeUnderstandingResult(subissue=replace(subissue, run=run))
