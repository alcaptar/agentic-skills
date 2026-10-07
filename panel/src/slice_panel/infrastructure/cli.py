from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_panel.domain.call_budget import CallBudget
from slice_panel.infrastructure.exit_code import ExitCode
from slice_panel.infrastructure.herdr_tabs import HerdrTabs
from slice_panel.infrastructure.panel_app import PanelApp
from slice_panel.infrastructure.subprocess_follow_source import SubprocessFollowSource
from slice_panel.infrastructure.subprocess_process_launcher import SubprocessProcessLauncher

if TYPE_CHECKING:
    from slice_panel.domain.follow_source import FollowSource
    from slice_panel.domain.process_launcher import ProcessLauncher


class Cli:
    FOLLOW_ARGV: ClassVar[tuple[str, ...]] = ("slice-runner", "follow", "--json")
    ROOT_ARGV: ClassVar[tuple[str, ...]] = ("git", "rev-parse", "--show-toplevel")
    REPO_ARGV: ClassVar[tuple[str, ...]] = ("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    WORKSPACE_VARIABLE: ClassVar[str] = "HERDR_WORKSPACE_ID"
    SECONDS_PER_CALL: ClassVar[float] = 60.0

    @classmethod
    def follow_source(cls) -> FollowSource:
        return SubprocessFollowSource(argv=cls.FOLLOW_ARGV)

    @classmethod
    def main(cls) -> int:
        if shutil.which("herdr") is None:
            sys.stderr.write("slice-panel needs herdr to open the runs in tabs, and it is not on the PATH\n")

            return ExitCode.HERDR_MISSING
        workspace = os.environ.get(cls.WORKSPACE_VARIABLE, "")
        if not workspace:
            sys.stderr.write(
                f"slice-panel must be started inside a herdr workspace: {cls.WORKSPACE_VARIABLE} is not set\n"
            )

            return ExitCode.WORKSPACE_UNKNOWN
        launcher = SubprocessProcessLauncher(budget=CallBudget(seconds_per_call=cls.SECONDS_PER_CALL))
        try:
            clone_root, repo = asyncio.run(cls._clone_of(launcher))
        except OSError as error:
            sys.stderr.write(f"slice-panel must be started inside the clone it launches runs from: {error}\n")

            return ExitCode.CLONE_UNKNOWN
        PanelApp(
            source=cls.follow_source(),
            launcher=launcher,
            tabs=HerdrTabs(launcher=launcher, workspace=workspace),
            clone_root=clone_root,
            repo=repo,
        ).run()

        return ExitCode.OK

    @classmethod
    async def _clone_of(cls, launcher: ProcessLauncher) -> tuple[Path, str]:
        root = await cls._answer_of(launcher, cls.ROOT_ARGV)
        repo = await cls._answer_of(launcher, cls.REPO_ARGV)

        return Path(root), repo

    @staticmethod
    async def _answer_of(launcher: ProcessLauncher, argv: tuple[str, ...]) -> str:
        outcome = await launcher.ran(argv)
        if outcome.exit_code != 0 or not outcome.stdout.strip():
            raise OSError(f"`{' '.join(argv)}` said: {outcome.stderr or 'nothing'}")

        return outcome.stdout.strip()
