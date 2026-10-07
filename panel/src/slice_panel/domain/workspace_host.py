from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from slice_panel.domain.created_workspace import CreatedWorkspace
    from slice_panel.domain.server_state import ServerState


class WorkspaceHost(ABC):
    @abstractmethod
    async def server_state(self) -> ServerState: ...

    @abstractmethod
    async def started_server(self) -> None: ...

    @abstractmethod
    async def workspaces_labelled(self, label: str) -> tuple[str, ...]: ...

    @abstractmethod
    async def pane_cwds_of(self, workspace: str) -> tuple[Path, ...]: ...

    @abstractmethod
    async def created_workspace(self, *, root: Path, label: str) -> CreatedWorkspace: ...

    @abstractmethod
    async def started_agent(self, *, name: str, pane: str) -> None: ...

    @abstractmethod
    async def split_right(self, pane: str) -> str: ...

    @abstractmethod
    async def ran_in(self, *, pane: str, command: Sequence[str]) -> None: ...

    @abstractmethod
    async def focused(self, workspace: str) -> None: ...

    @abstractmethod
    async def closed_workspace(self, workspace: str) -> None: ...

    @abstractmethod
    async def attached(self) -> NoReturn: ...
