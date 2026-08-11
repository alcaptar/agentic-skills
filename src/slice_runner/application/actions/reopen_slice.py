from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import ImpossibleTransitionError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.run_state import RunState

if TYPE_CHECKING:
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.state_machine import StateMachine
    from slice_runner.domain.sub_issue import SubIssue


@dataclass(frozen=True, kw_only=True, slots=True)
class ReopenSliceParams:
    repo: str
    subissue: SubIssue
    instruction: str


@dataclass(frozen=True, kw_only=True, slots=True)
class ReopenSliceResult:
    subissue: SubIssue
    instruction: str


class ReopenSlice:
    def __init__(self, *, repository: RunRepository, machine: StateMachine) -> None:
        self._repository = repository
        self._machine = machine

    def execute(self, params: ReopenSliceParams) -> ReopenSliceResult:
        subissue = params.subissue
        if subissue.run is None or subissue.label is None:
            raise ImpossibleTransitionError(
                f"subissue #{subissue.number} cannot be reopened without a closed run and a blocking label"
            )

        run = self._machine.reopened(subissue.run, blocked=subissue.label)
        label = IssueLabel.of(state=RunState.OPEN, step=run.step)
        if label is None:
            raise ImpossibleTransitionError(f"the step `{run.step}` of an open run maps to no label")

        self._repository.write_run(repo=params.repo, issue=subissue.number, run=run)
        self._repository.write_label(repo=params.repo, issue=subissue.number, remove=subissue.label, add=label)
        self._repository.mark_reopened(repo=params.repo, issue=subissue.number, instruction=params.instruction)

        return ReopenSliceResult(subissue=replace(subissue, run=run, label=label), instruction=params.instruction)
