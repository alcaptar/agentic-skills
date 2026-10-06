from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_panel.domain.event_status import EventStatus

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowLine:
    ts: datetime
    repo: str
    issue: int
    slice_id: str
    step: str
    status: str
    cost_usd: float
    parent: int | None = None
    name: str | None = None

    def awaits_a_person(self) -> bool:
        return self.status == EventStatus.AWAITING_PERSON
