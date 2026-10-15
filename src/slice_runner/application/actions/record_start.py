from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.event import Event
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step

if TYPE_CHECKING:
    from slice_runner.domain.clock import Clock
    from slice_runner.domain.event_log import EventLog
    from slice_runner.domain.feature_slice import FeatureSlice
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.run import Run


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordStartParams:
    repo: str
    issue: int
    slice_id: str
    run: Run
    spend: HarnessSpend
    feature_slice: FeatureSlice


class RecordStart:
    def __init__(self, *, events: EventLog, clock: Clock) -> None:
        self._events = events
        self._clock = clock

    def execute(self, params: RecordStartParams) -> None:
        if params.run.step is Step.AWAIT_CI or params.run.step is Step.AWAIT_MERGE:
            return

        self._events.emit(
            Event(
                slice_id=params.slice_id,
                repo=params.repo,
                issue=params.issue,
                step=params.run.step,
                at=self._clock.now(),
                spend=params.spend,
                status=EventStatus.ADVANCING,
                state=RunState.OPEN,
                feature_slice=params.feature_slice,
            )
        )
