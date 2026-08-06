from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.event_status import EventStatus
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.step import Step


@dataclass(frozen=True, kw_only=True, slots=True)
class Event:
    slice_id: str
    step: Step
    at: datetime
    spend: HarnessSpend
    status: EventStatus
