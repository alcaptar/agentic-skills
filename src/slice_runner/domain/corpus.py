from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry


class Corpus(ABC):
    @abstractmethod
    def record(self, entry: CorpusEntry) -> None: ...
