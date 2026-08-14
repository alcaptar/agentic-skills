from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class Provenance(ABC):
    @abstractmethod
    def checkout(self) -> Path: ...
