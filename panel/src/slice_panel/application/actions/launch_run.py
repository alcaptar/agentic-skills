from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_panel.domain.exceptions import FeatureUnknownError

if TYPE_CHECKING:
    from pathlib import Path

    from slice_panel.domain.run_tabs import RunTabs
    from slice_panel.domain.slice_view import SliceView
    from slice_panel.domain.tab_handle import TabHandle


@dataclass(frozen=True, kw_only=True, slots=True)
class LaunchRunParams:
    view: SliceView


class LaunchRun:
    def __init__(self, *, tabs: RunTabs, clone_root: Path) -> None:
        self._tabs = tabs
        self._clone_root = clone_root

    async def execute(self, params: LaunchRunParams) -> TabHandle:
        view = params.view
        if view.parent is None:
            raise FeatureUnknownError(view.slice_id)

        return await self._tabs.opened_run_of(
            repo=view.repo, parent=view.parent, slice_id=view.slice_id, cwd=self._clone_root
        )
