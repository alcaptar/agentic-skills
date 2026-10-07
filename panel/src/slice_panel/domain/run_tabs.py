from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from slice_panel.domain.tab_handle import TabHandle


class RunTabs(ABC):
    @abstractmethod
    async def opened_run_of(self, *, repo: str, parent: int, slice_id: str, cwd: Path) -> TabHandle: ...

    @abstractmethod
    async def focused(self, handle: TabHandle) -> None: ...
