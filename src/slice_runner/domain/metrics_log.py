from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.closed_slice_record import ClosedSliceRecord


class MetricsLog(ABC):
    @abstractmethod
    def record(self, closed: ClosedSlice) -> None: ...

    @abstractmethod
    def closed_slices(self, *, repo: str | None, since: datetime, until: datetime) -> tuple[ClosedSliceRecord, ...]: ...
