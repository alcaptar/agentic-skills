from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.closed_slice_record import ClosedSliceRecord
    from slice_runner.domain.metrics_log import MetricsLog


@dataclass(frozen=True, kw_only=True, slots=True)
class ListClosedSlicesParams:
    repo: str | None
    since: datetime
    until: datetime


class ListClosedSlices:
    def __init__(self, *, metrics_log: MetricsLog) -> None:
        self._metrics_log = metrics_log

    def execute(self, params: ListClosedSlicesParams) -> tuple[ClosedSliceRecord, ...]:
        return self._metrics_log.closed_slices(repo=params.repo, since=params.since, until=params.until)
