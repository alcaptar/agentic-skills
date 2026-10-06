from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, ClassVar

from slice_panel.domain.tab_handle import TabHandle
from slice_panel.infrastructure.herdr_tab_created_payload import HerdrTabCreatedPayload

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from slice_panel.infrastructure.process_launcher import ProcessLauncher
    from slice_panel.infrastructure.process_outcome import ProcessOutcome


class HerdrFailedError(OSError):
    pass


class HerdrTabs:
    EXECUTABLE: ClassVar[str] = "herdr"

    def __init__(self, *, launcher: ProcessLauncher) -> None:
        self._launcher = launcher

    async def opened(self, command: Sequence[str], *, cwd: Path, label: str) -> TabHandle:
        created = self._succeeded(
            await self._launcher.ran(
                (self.EXECUTABLE, "tab", "create", "--cwd", str(cwd), "--label", label, "--no-focus")
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
