from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class EventFollowLinePayload(ContractModel):
    VERSION: ClassVar[int] = 1

    version: int
    ts: str
    repo: str
    issue: int
    slice_id: str
    step: Step
    status: EventStatus
    cost_usd: float
    closed_as: RunState | None = None
    parent: int | None = None
    name: str | None = None

    @classmethod
    def from_domain(cls, event: Event) -> Self:
        return cls(
            version=cls.VERSION,
            ts=event.at.isoformat(),
            repo=event.repo,
            issue=event.issue,
            slice_id=event.slice_id,
            step=event.step,
            status=event.status,
            cost_usd=event.spend.cost_usd,
            closed_as=None if event.state is RunState.OPEN else event.state,
            parent=None if event.feature_slice is None else event.feature_slice.parent,
            name=None if event.feature_slice is None else event.feature_slice.name,
        )
