from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Self

from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.spend_payload import SpendPayload

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class EventPayload(ContractModel):
    slice_id: str
    step: Step
    at: datetime
    spend: SpendPayload
    status: EventStatus

    @classmethod
    def from_domain(cls, event: Event) -> Self:
        return cls(
            slice_id=event.slice_id,
            step=event.step,
            at=event.at,
            spend=SpendPayload.from_domain(event.spend),
            status=event.status,
        )
