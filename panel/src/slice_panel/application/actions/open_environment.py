from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, NoReturn

from slice_panel.domain.exceptions import ServerDidNotStartError
from slice_panel.domain.server_state import ServerState

if TYPE_CHECKING:
    from pathlib import Path

    from slice_panel.domain.clock import Clock
    from slice_panel.domain.server_wait import ServerWait
    from slice_panel.domain.workspace_host import WorkspaceHost


@dataclass(frozen=True, kw_only=True, slots=True)
class OpenEnvironmentParams:
    clone_root: Path


class OpenEnvironment:
    COORDINATOR: ClassVar[str] = "coordinador"
    PANEL_COMMAND: ClassVar[tuple[str, ...]] = ("slice-panel",)

    def __init__(self, *, host: WorkspaceHost, clock: Clock, wait: ServerWait) -> None:
        self._host = host
        self._clock = clock
        self._wait = wait

    async def execute(self, params: OpenEnvironmentParams) -> NoReturn:
        if await self._host.server_state() is ServerState.STOPPED:
            await self._host.started_server()
            await self._waited_for_the_server()
        workspace = await self._workspace_of(params)
        await self._host.focused(workspace)
        await self._host.attached()

    async def _workspace_of(self, params: OpenEnvironmentParams) -> str:
        label = params.clone_root.name
        for candidate in await self._host.workspaces_labelled(label):
            if params.clone_root in await self._host.pane_cwds_of(candidate):
                return candidate
        created = await self._host.created_workspace(root=params.clone_root, label=label)
        await self._host.started_agent(name=self.COORDINATOR, pane=created.root_pane)
        panel_pane = await self._host.split_right(created.root_pane)
        await self._host.ran_in(pane=panel_pane, command=self.PANEL_COMMAND)

        return created.workspace_id

    async def _waited_for_the_server(self) -> None:
        deadline = self._clock.now() + self._wait.deadline_seconds
        while True:
            await self._clock.sleep(self._wait.poll_seconds)
            if await self._host.server_state() is ServerState.RUNNING:
                return
            if self._clock.now() >= deadline:
                raise ServerDidNotStartError(self._wait.deadline_seconds)
