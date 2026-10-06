from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.installed_code_match import InstalledCodeMatch


class InstalledCode(ABC):
    @abstractmethod
    def compared_with(self, *, checkout: Path) -> InstalledCodeMatch: ...
