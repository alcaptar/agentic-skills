from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class Corpus(ABC):
    @abstractmethod
    def record(self, entry: CorpusEntry) -> None: ...

    @abstractmethod
    def size_of_the_last_verification(self, coordinates: SliceCoordinates) -> DiffStats | None: ...
