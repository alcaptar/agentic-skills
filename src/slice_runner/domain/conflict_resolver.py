from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.merge_conflict import MergeConflict
    from slice_runner.domain.resolution import Resolution


class ConflictResolver(ABC):
    @abstractmethod
    def resolve(self, conflict: MergeConflict) -> Resolution: ...
