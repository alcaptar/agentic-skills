from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from slice_panel.infrastructure.process_outcome import ProcessOutcome


class ProcessTimedOutError(OSError):
    def __init__(self, argv: Sequence[str], seconds: float) -> None:
        super().__init__(f"`{' '.join(argv)}` did not finish in {seconds:g}s")


class ProcessLauncher(ABC):
    @abstractmethod
    async def ran(self, argv: Sequence[str], *, cwd: Path | None = None) -> ProcessOutcome: ...
