from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.event import Event
from slice_runner.domain.event_cursor import EventCursor
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.feature_slice import FeatureSlice
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from slice_runner.domain.child_issue import ChildIssue
    from slice_runner.domain.child_issues import ChildIssues
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.event_log import EventLog
    from slice_runner.domain.event_reader import EventReader


@dataclass(frozen=True, kw_only=True, slots=True)
class RegisterPendingSlicesParams:
    repo: str
    parent: int


@dataclass(frozen=True, kw_only=True, slots=True)
class RegisterPendingSlicesResult:
    registered: tuple[Event, ...]


class RegisterPendingSlices:
    def __init__(self, *, children: ChildIssues, reader: EventReader, log: EventLog, clock: Clock) -> None:
        self._children = children
        self._reader = reader
        self._log = log
        self._clock = clock

    def execute(self, params: RegisterPendingSlicesParams) -> RegisterPendingSlicesResult:
        started = {event.slice_key for event in self._reader.read_since(EventCursor.start()).events}
        pending = tuple(
            self._pending_event_of(child, params)
            for child in self._children.of_parent(repo=params.repo, parent=params.parent)
            if child.state is IssueState.OPEN
        )
        registered = tuple(event for event in pending if event.slice_key not in started)
        for event in registered:
            self._log.emit(event)

        return RegisterPendingSlicesResult(registered=registered)

    def _pending_event_of(self, child: ChildIssue, params: RegisterPendingSlicesParams) -> Event:
        return Event(
            slice_id=child.slice_id.canonical,
            repo=params.repo,
            issue=child.number,
            step=Step.MOUNT_WORKTREE,
            at=self._clock.now(),
            spend=HarnessSpend.nothing(),
            status=EventStatus.PENDING,
            state=RunState.OPEN,
            feature_slice=FeatureSlice(parent=params.parent, name=child.slice_id.name),
        )
