from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, ClassVar

from slice_panel.domain.run_tabs import RunTabs
from slice_panel.domain.tab_handle import TabHandle
from slice_panel.infrastructure.herdr_tab_created_payload import HerdrTabCreatedPayload
from slice_panel.infrastructure.slice_runner_commands import SliceRunnerCommands

if TYPE_CHECKING:
    from pathlib import Path

    from slice_panel.domain.process_launcher import ProcessLauncher
    from slice_panel.domain.process_outcome import ProcessOutcome


class HerdrFailedError(OSError):
    pass


class HerdrTabs(RunTabs):
    EXECUTABLE: ClassVar[str] = "herdr"

    def __init__(self, *, launcher: ProcessLauncher, workspace: str) -> None:
        self._launcher = launcher
        self._workspace = workspace

    async def opened_run_of(self, *, repo: str, parent: int, slice_id: str, cwd: Path) -> TabHandle:
        command = SliceRunnerCommands.run(repo=repo, parent=parent, slice_id=slice_id)
        created = self._succeeded(
            await self._launcher.ran(
                (
                    self.EXECUTABLE,
                    "tab",
                    "create",
                    "--cwd",
                    str(cwd),
                    "--workspace",
                    self._workspace,
                    "--label",
                    slice_id,
                    "--no-focus",
                )
            )
        )
        payload = HerdrTabCreatedPayload.parsed(created.stdout)
        self._succeeded(
            await self._launcher.ran((self.EXECUTABLE, "pane", "run", payload.pane_id, shlex.join(command)))
        )

        return TabHandle(tab_id=payload.tab_id)

    async def focused(self, handle: TabHandle) -> None:
        self._succeeded(await self._launcher.ran((self.EXECUTABLE, "tab", "focus", handle.tab_id)))

    @staticmethod
    def _succeeded(outcome: ProcessOutcome) -> ProcessOutcome:
        if outcome.exit_code != 0:
            raise HerdrFailedError(f"herdr failed: {outcome.stderr or outcome.stdout}")

        return outcome
