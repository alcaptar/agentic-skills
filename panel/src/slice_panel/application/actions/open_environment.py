from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, NoReturn, TypeVar

from slice_panel.domain.coordinator_name import CoordinatorName
from slice_panel.domain.exceptions import (
    AgentNameTakenError,
    MountingAndCleanupFailedError,
    MountingFailedError,
    NoFreeAgentNameError,
    ServerDidNotStartError,
)
from slice_panel.domain.mounting_step import MountingStep
from slice_panel.domain.server_state import ServerState

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from pathlib import Path

    from slice_panel.domain.clock import Clock
    from slice_panel.domain.server_wait import ServerWait
    from slice_panel.domain.workspace_host import WorkspaceHost

Outcome = TypeVar("Outcome")


@dataclass(frozen=True, kw_only=True, slots=True)
class OpenEnvironmentParams:
    clone_root: Path


class OpenEnvironment:
    PANEL_COMMAND: ClassVar[tuple[str, ...]] = ("slice-panel",)

    def __init__(self, *, host: WorkspaceHost, clock: Clock, wait: ServerWait) -> None:
        self._host = host
        self._clock = clock
        self._wait = wait

    async def execute(self, params: OpenEnvironmentParams) -> NoReturn:
        if await self._host.server_state() is ServerState.STOPPED:
            await self._host.started_server()
            await self._waited_for_the_server()
        reused = await self._reused_workspace(params)
        if reused is not None:
            await self._during(MountingStep.FOCUS, self._host.focused(reused))
        else:
            await self._mounted_and_focused(params)
        await self._host.attached()

    async def _reused_workspace(self, params: OpenEnvironmentParams) -> str | None:
        for candidate in await self._host.workspaces_labelled(params.clone_root.name):
            if params.clone_root in await self._host.pane_cwds_of(candidate):
                return candidate

        return None

    async def _mounted_and_focused(self, params: OpenEnvironmentParams) -> None:
        created = await self._host.created_workspace(root=params.clone_root, label=params.clone_root.name)
        try:
            await self._during(
                MountingStep.START_COORDINATOR, self._started_coordinator(params.clone_root, created.root_pane)
            )
            panel_pane = await self._during(MountingStep.SPLIT_PANE, self._host.split_right(created.root_pane))
            await self._during(MountingStep.RUN_PANEL, self._host.ran_in(pane=panel_pane, command=self.PANEL_COMMAND))
            await self._during(MountingStep.FOCUS, self._host.focused(created.workspace_id))
        except MountingFailedError as failure:
            raise await self._after_closing(created.workspace_id, failure) from failure

    async def _started_coordinator(self, clone_root: Path, pane: str) -> None:
        candidates = CoordinatorName.of_the_clone(clone_root).candidates
        for name in candidates:
            try:
                await self._host.started_agent(name=name, pane=pane)
            except AgentNameTakenError:
                continue
            return
        raise NoFreeAgentNameError(candidates)

    async def _after_closing(self, workspace: str, failure: MountingFailedError) -> MountingFailedError:
        try:
            await self._host.closed_workspace(workspace)
        except OSError as error:
            return MountingAndCleanupFailedError(failure.step, failure.reason, str(error))

        return failure

    @staticmethod
    async def _during(step: MountingStep, operation: Awaitable[Outcome]) -> Outcome:
        try:
            return await operation
        except OSError as error:
            raise MountingFailedError(step, str(error)) from error

    async def _waited_for_the_server(self) -> None:
        deadline = self._clock.now() + self._wait.deadline_seconds
        while True:
            await self._clock.sleep(self._wait.poll_seconds)
            if await self._host.server_state() is ServerState.RUNNING:
                return
            if self._clock.now() >= deadline:
                raise ServerDidNotStartError(self._wait.deadline_seconds)
