from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Self

from slice_runner.domain.canonical_slice_id import CanonicalSliceId
from slice_runner.domain.event import Event
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.exceptions import UnreadableEventLogError
from slice_runner.domain.slice_coordinates import SliceCoordinates
from slice_runner.domain.step import Step
from slice_runner.infrastructure.durable_ledger import ReadableLedgerRow
from slice_runner.infrastructure.json_schema import JsonSchema
from slice_runner.infrastructure.spend_payload import SpendPayload
from slice_runner.infrastructure.stamped_row import StampedRow


class EventPayload(StampedRow, ReadableLedgerRow):
    UNREADABLE: ClassVar[type[ValueError]] = UnreadableEventLogError

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

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            data, "the event log line is not one this program wrote in this generation", cls.UNREADABLE
        )

    def to_domain(self) -> Event:
        return Event(
            slice_id=self.slice_id,
            repo=self.repo,
            issue=self.issue,
            step=self.step,
            at=datetime.fromisoformat(self.ts),
            spend=self.spend.to_domain(),
            status=self.status,
        )
