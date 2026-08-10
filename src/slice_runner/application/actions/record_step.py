from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from slice_runner.domain.event import Event
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.issue_label import IssueLabel

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.event_log import EventLog
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.run import Run
    from slice_runner.domain.run_repository import RunRepository
    from slice_runner.domain.transition import Transition


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordStepParams:
    repo: str
    issue: int
    slice_id: str
    current: Run
    label: IssueLabel | None
    transition: Transition
    spend: HarnessSpend


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordStepResult:
    run: Run
    label: IssueLabel | None


class RecordStep:
    def __init__(self, *, repository: RunRepository, events: EventLog, clock: Clock) -> None:
        self._repository = repository
        self._events = events
        self._clock = clock

    def execute(self, params: RecordStepParams) -> RecordStepResult:
        run = replace(params.transition.run, spend=params.spend)
        if run != params.current:
            self._repository.write_run(repo=params.repo, issue=params.issue, run=run)
        label = self._labelled(params, step_of=run)
        self._emit(params, run=run)

        return RecordStepResult(run=run, label=label)

    def _labelled(self, params: RecordStepParams, *, step_of: Run) -> IssueLabel | None:
        label = IssueLabel.of(state=params.transition.state, step=step_of.step)
        if label is params.label:
            return label
        if label is None:
            if params.label is not None:
                self._repository.remove_label(repo=params.repo, issue=params.issue, remove=params.label)

            return None

        self._repository.write_label(repo=params.repo, issue=params.issue, remove=params.label, add=label)

        return label

    def _emit(self, params: RecordStepParams, *, run: Run) -> None:
        self._events.emit(
            Event(
                slice_id=params.slice_id,
                step=run.step,
                at=self._clock.now(),
                spend=params.spend,
                status=EventStatus.of_the_transition(params.transition),
            )
        )
