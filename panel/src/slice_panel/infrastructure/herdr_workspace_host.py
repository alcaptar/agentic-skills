from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, ClassVar, NoReturn

from slice_panel.domain.exceptions import AgentNameTakenError
from slice_panel.domain.workspace_host import WorkspaceHost
from slice_panel.infrastructure.herdr_error_payload import HerdrErrorPayload
from slice_panel.infrastructure.herdr_pane_list_payload import HerdrPaneListPayload
from slice_panel.infrastructure.herdr_pane_split_payload import HerdrPaneSplitPayload
from slice_panel.infrastructure.herdr_server_status import HerdrServerStatus
from slice_panel.infrastructure.herdr_tabs import HerdrFailedError
from slice_panel.infrastructure.herdr_workspace_created_payload import HerdrWorkspaceCreatedPayload
from slice_panel.infrastructure.herdr_workspace_list_payload import HerdrWorkspaceListPayload

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from slice_panel.domain.created_workspace import CreatedWorkspace
    from slice_panel.domain.process_launcher import ProcessLauncher
    from slice_panel.domain.process_outcome import ProcessOutcome
    from slice_panel.domain.server_state import ServerState
    from slice_panel.infrastructure.unbounded_processes import UnboundedProcesses


class HerdrWorkspaceHost(WorkspaceHost):
    EXECUTABLE: ClassVar[str] = "herdr"
    AGENT_NAME_TAKEN: ClassVar[str] = "agent_name_taken"

    def __init__(self, *, launcher: ProcessLauncher, unbounded: UnboundedProcesses) -> None:
        self._launcher = launcher
        self._unbounded = unbounded

    async def server_state(self) -> ServerState:
        outcome = await self._launcher.ran((self.EXECUTABLE, "status", "server"))
        if outcome.exit_code != 0 and outcome.stderr:
            raise HerdrFailedError(f"herdr failed: {outcome.stderr}")

        return HerdrServerStatus.state_of(outcome.stdout)

    async def started_server(self) -> None:
        self._unbounded.spawned_detached((self.EXECUTABLE, "server"))

    async def workspaces_labelled(self, label: str) -> tuple[str, ...]:
        listed = await self._succeeded("workspace", "list")

        return HerdrWorkspaceListPayload.parsed(listed.stdout).labelled(label)

    async def pane_cwds_of(self, workspace: str) -> tuple[Path, ...]:
        listed = await self._succeeded("pane", "list", "--workspace", workspace)

        return HerdrPaneListPayload.parsed(listed.stdout).cwds

    async def created_workspace(self, *, root: Path, label: str) -> CreatedWorkspace:
        created = await self._succeeded("workspace", "create", "--cwd", str(root), "--label", label, "--no-focus")

        return HerdrWorkspaceCreatedPayload.parsed(created.stdout).to_domain()

    async def started_agent(self, *, name: str, pane: str) -> None:
        argv = (self.EXECUTABLE, "agent", "start", name, "--kind", "claude", "--pane", pane)
        outcome = await self._launcher.ran(argv)
        if outcome.exit_code != 0 and HerdrErrorPayload.code_of(outcome) == self.AGENT_NAME_TAKEN:
            raise AgentNameTakenError(name)
        self._checked(outcome)

    async def split_right(self, pane: str) -> str:
        split = await self._succeeded("pane", "split", pane, "--direction", "right", "--no-focus")

        return HerdrPaneSplitPayload.parsed(split.stdout).pane_id

    async def ran_in(self, *, pane: str, command: Sequence[str]) -> None:
        await self._succeeded("pane", "run", pane, shlex.join(command))

    async def focused(self, workspace: str) -> None:
        await self._succeeded("workspace", "focus", workspace)

    async def closed_workspace(self, workspace: str) -> None:
        await self._succeeded("workspace", "close", workspace)

    async def attached(self) -> NoReturn:
        self._unbounded.replaced_by((self.EXECUTABLE,))

    async def _succeeded(self, *arguments: str) -> ProcessOutcome:
        return self._checked(await self._launcher.ran((self.EXECUTABLE, *arguments)))

    @staticmethod
    def _checked(outcome: ProcessOutcome) -> ProcessOutcome:
        if outcome.exit_code != 0:
            raise HerdrFailedError(f"herdr failed: {outcome.stderr or outcome.stdout}")

        return outcome
