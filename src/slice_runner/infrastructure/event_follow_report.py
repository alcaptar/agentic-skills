from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class EventFollowReport:
    def __init__(self, *, events: tuple[Event, ...]) -> None:
        self._events = events

    def lines(self) -> tuple[str, ...]:
        return tuple(self._line_of(event) for event in self._events)

    @staticmethod
    def _line_of(event: Event) -> str:
        line = (
            f"{event.at.isoformat()} {event.repo} #{event.issue} {event.slice_id} "
            f"{event.step} {event.status} ${event.spend.cost_usd:.2f}"
        )
        if event.closed_as is None:
            return line

        return f"{line} {event.closed_as}"
