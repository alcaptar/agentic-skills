from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_panel.application.actions.launch_run import LaunchRunParams
from slice_panel.domain.exceptions import OrderRefusedError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from slice_panel.application.actions.launch_run import LaunchRun
    from slice_panel.domain.process_launcher import ProcessLauncher
    from slice_panel.domain.slice_view import SliceView
    from slice_panel.domain.tab_handle import TabHandle


@dataclass(frozen=True, kw_only=True, slots=True)
class GiveOrderParams:
    view: SliceView
    order: Sequence[str]


class GiveOrder:
    SUCCESS: int = 0

    def __init__(self, *, launcher: ProcessLauncher, launch: LaunchRun, clone_root: Path) -> None:
        self._launcher = launcher
        self._launch = launch
        self._clone_root = clone_root

    async def execute(self, params: GiveOrderParams) -> TabHandle:
        outcome = await self._launcher.ran(params.order, cwd=self._clone_root)
        if outcome.exit_code != self.SUCCESS:
            raise OrderRefusedError(outcome, params.order)

        return await self._launch.execute(LaunchRunParams(view=params.view))
