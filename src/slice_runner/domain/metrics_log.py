from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice


class MetricsLog(ABC):
    @abstractmethod
    def record(self, closed: ClosedSlice) -> None: ...
