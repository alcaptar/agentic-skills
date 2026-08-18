from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from slice_runner.domain.alignment import Alignment
from slice_runner.domain.alignment_response_kind import AlignmentResponseKind
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.run import Run
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.domain.understanding_writer import UnderstandingWriter


@dataclass(frozen=True, kw_only=True, slots=True)
class SeekAlignmentParams:
    repo: str
    worktree: str
    subissue: SubIssue
    parent: ParentIssue
    run: Run
    understanding: str = ""


@dataclass(frozen=True, kw_only=True, slots=True)
class SeekAlignmentResult:
    run: Run
    understanding: str
    response: AlignmentResponseKind | None = None
    spend: HarnessSpend | None = None


class SeekAlignment:
    def __init__(self, *, understanding: UnderstandingWriter, repository: RunRepository) -> None:
        self._understanding = understanding
        self._repository = repository

    def execute(self, params: SeekAlignmentParams) -> SeekAlignmentResult:
        if params.run.understanding_pending:
            return self._published(params, agreed=params.understanding, correction="")

        response = self._repository.read_alignment_response(repo=params.repo, issue=params.subissue.number)
        if response.kind is AlignmentResponseKind.REVIEW and response.correction != params.run.corrected:
            seeded = self._seeded(params)
            published = self._published(seeded, agreed=seeded.understanding, correction=response.correction)

            return replace(published, response=response.kind)
        if response.kind is AlignmentResponseKind.MALFORMED and response.reason is not None:
            self._repository.write_malformed_response(
                repo=params.repo, issue=params.subissue.number, reason=response.reason
            )

        return SeekAlignmentResult(run=params.run, understanding=params.understanding, response=response.kind)

    def _published(self, params: SeekAlignmentParams, *, agreed: str, correction: str) -> SeekAlignmentResult:
        understanding = self._understanding.write(
            subissue=params.subissue,
            parent=params.parent,
            repo=params.repo,
            worktree=params.worktree,
            alignment=Alignment(agreed=agreed, correction=correction),
        )
        run = replace(
            params.run,
            step=Step.UNDERSTAND,
            spend=params.run.spend.plus(understanding.spend),
            corrected=correction,
            understanding_pending=False,
        )
        self._repository.write_run(repo=params.repo, issue=params.subissue.number, run=run)
        self._repository.write_understanding(
            repo=params.repo, issue=params.subissue.number, understanding=understanding.text
        )

        return SeekAlignmentResult(run=run, understanding=understanding.text, spend=understanding.spend)

    def _seeded(self, params: SeekAlignmentParams) -> SeekAlignmentParams:
        if params.understanding:
            return params

        agreed = self._repository.read_understanding(repo=params.repo, issue=params.subissue.number)

        return replace(params, understanding=agreed)
