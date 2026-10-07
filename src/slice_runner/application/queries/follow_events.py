from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.event import Event
    from slice_runner.domain.event_cursor import EventCursor
    from slice_runner.domain.event_reader import EventReader


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowEventsParams:
    cursor: EventCursor
    snapshot: tuple[Event, ...] = ()
    repo: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowEventsResult:
    snapshot: tuple[Event, ...]
    changes: tuple[Event, ...]
    cursor: EventCursor


class FollowEvents:
    def __init__(self, *, reader: EventReader) -> None:
        self._reader = reader

    def execute(self, params: FollowEventsParams) -> FollowEventsResult:
        batch = self._reader.read_since(params.cursor)
        latest = {self._slice_of(event): event for event in params.snapshot}
        changes: list[Event] = []
        for event in batch.events:
            if params.repo is not None and event.repo != params.repo:
                continue
            if self._differs_from(latest.get(self._slice_of(event)), event):
                changes.append(event)
            latest[self._slice_of(event)] = event

        return FollowEventsResult(snapshot=tuple(latest.values()), changes=tuple(changes), cursor=batch.cursor)

    @staticmethod
    def _slice_of(event: Event) -> tuple[str, int, str]:
        return event.repo, event.issue, event.slice_id

    @staticmethod
    def _differs_from(previous: Event | None, event: Event) -> bool:
        if previous is None:
            return True

        return (previous.step, previous.status, previous.state) != (event.step, event.status, event.state)
