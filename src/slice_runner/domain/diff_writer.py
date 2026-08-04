from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.diff_on_disk import DiffOnDisk


class DiffWriter(ABC):
    @abstractmethod
    def write(self, *, repo: str, base: str) -> DiffOnDisk: ...
