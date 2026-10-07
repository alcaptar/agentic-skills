from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from slice_panel.domain.process_outcome import ProcessOutcome


class ProcessLauncher(ABC):
    @abstractmethod
    async def ran(self, argv: Sequence[str], *, cwd: Path | None = None) -> ProcessOutcome: ...
