from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.spend_payload import SpendPayload
from slice_runner.infrastructure.stamped_row import StampedRow

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class EventPayload(StampedRow):
    step: Step
    spend: SpendPayload
    status: EventStatus

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, event: Event) -> Self:
        coordinates = SliceCoordinates(
            repo=event.repo, issue=event.issue, slice_id=CanonicalSliceId.of_text(event.slice_id)
        )

        return cls._stamped(
            coordinates,
            ts=event.at.isoformat(),
            step=event.step,
            spend=SpendPayload.from_domain(event.spend),
            status=event.status,
        )
