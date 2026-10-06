from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.branch_standing import BranchStanding
from slice_runner.domain.event import Event
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.event_log import EventLog
    from slice_runner.domain.feature_slice import FeatureSlice
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.workspace import Workspace


@dataclass(frozen=True, kw_only=True, slots=True)
class CommitRoundParams:
    worktree: str
    branch: str
    message: str
    repo: str
    issue: int
    slice_id: str
    spend: HarnessSpend
    feature_slice: FeatureSlice


class CommitRound:
    def __init__(self, *, workspace: Workspace, events: EventLog, clock: Clock) -> None:
        self._workspace = workspace
        self._events = events
        self._clock = clock

    def execute(self, params: CommitRoundParams) -> None:
        standing_on = self._workspace.current_branch(worktree=params.worktree)
        BranchStanding.of(standing_on=standing_on, declared=params.branch).raise_unless_ok(action="commit")

        if not self._workspace.staged(worktree=params.worktree):
            self._events.emit(
                Event(
                    slice_id=params.slice_id,
                    repo=params.repo,
                    issue=params.issue,
                    step=Step.RUN_CONTROLS,
                    at=self._clock.now(),
                    spend=params.spend,
                    status=EventStatus.NOTHING_TO_COMMIT,
                    state=RunState.OPEN,
                    feature_slice=params.feature_slice,
                )
            )

            return

        self._workspace.commit(worktree=params.worktree, message=params.message)
