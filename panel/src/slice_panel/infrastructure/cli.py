from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_panel.application.actions.open_environment import OpenEnvironment, OpenEnvironmentParams
from slice_panel.domain.call_budget import CallBudget
from slice_panel.domain.exceptions import MountingFailedError, ServerDidNotStartError
from slice_panel.domain.server_wait import ServerWait
from slice_panel.infrastructure.asyncio_clock import AsyncioClock
from slice_panel.infrastructure.exit_code import ExitCode
from slice_panel.infrastructure.herdr_tabs import HerdrTabs
from slice_panel.infrastructure.herdr_workspace_host import HerdrWorkspaceHost
from slice_panel.infrastructure.os_unbounded_processes import OsUnboundedProcesses
from slice_panel.infrastructure.panel_app import PanelApp
from slice_panel.infrastructure.subprocess_follow_source import SubprocessFollowSource
from slice_panel.infrastructure.subprocess_process_launcher import SubprocessProcessLauncher

if TYPE_CHECKING:
    from slice_panel.domain.clock import Clock
    from slice_panel.domain.follow_source import FollowSource
    from slice_panel.domain.process_launcher import ProcessLauncher
    from slice_panel.infrastructure.unbounded_processes import UnboundedProcesses


class Cli:
    FOLLOW_ARGV: ClassVar[tuple[str, ...]] = ("slice-runner", "follow", "--json")
    ROOT_ARGV: ClassVar[tuple[str, ...]] = ("git", "rev-parse", "--show-toplevel")
    REPO_ARGV: ClassVar[tuple[str, ...]] = ("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    WORKSPACE_VARIABLE: ClassVar[str] = "HERDR_WORKSPACE_ID"
    SECONDS_PER_CALL: ClassVar[float] = 60.0
    SERVER_POLL_SECONDS: ClassVar[float] = 0.5
    SERVER_DEADLINE_SECONDS: ClassVar[float] = 10.0

    @classmethod
    def follow_source(cls) -> FollowSource:
        return SubprocessFollowSource(argv=cls.FOLLOW_ARGV)

    @classmethod
    def process_launcher(cls) -> ProcessLauncher:
        return SubprocessProcessLauncher(budget=CallBudget(seconds_per_call=cls.SECONDS_PER_CALL))

    @classmethod
    def main(cls) -> int:
        return cls.run(launcher=cls.process_launcher(), unbounded=OsUnboundedProcesses(), clock=AsyncioClock())

    @classmethod
    def run(cls, *, launcher: ProcessLauncher, unbounded: UnboundedProcesses, clock: Clock) -> int:
        if shutil.which("herdr") is None:
            sys.stderr.write("slice-panel needs herdr to open the runs in tabs, and it is not on the PATH\n")

            return ExitCode.HERDR_MISSING
        try:
            clone_root = Path(asyncio.run(cls._answer_of(launcher, cls.ROOT_ARGV)))
        except OSError as error:
            return cls._clone_unknown(error)
        workspace = os.environ.get(cls.WORKSPACE_VARIABLE, "")
        if not workspace:
            return cls._opened_environment(launcher=launcher, unbounded=unbounded, clock=clock, clone_root=clone_root)
        try:
            repo = asyncio.run(cls._answer_of(launcher, cls.REPO_ARGV))
        except OSError as error:
            return cls._clone_unknown(error)
        PanelApp(
            source=cls.follow_source(),
            launcher=launcher,
            tabs=HerdrTabs(launcher=launcher, workspace=workspace),
            clone_root=clone_root,
            repo=repo,
        ).run()

        return ExitCode.OK

    @staticmethod
    def _clone_unknown(error: OSError) -> int:
        sys.stderr.write(f"slice-panel must be started inside the clone it launches runs from: {error}\n")

        return ExitCode.CLONE_UNKNOWN

    @classmethod
    def _opened_environment(
        cls, *, launcher: ProcessLauncher, unbounded: UnboundedProcesses, clock: Clock, clone_root: Path
    ) -> int:
        environment = OpenEnvironment(
            host=HerdrWorkspaceHost(launcher=launcher, unbounded=unbounded),
            clock=clock,
            wait=ServerWait(poll_seconds=cls.SERVER_POLL_SECONDS, deadline_seconds=cls.SERVER_DEADLINE_SECONDS),
        )
        try:
            asyncio.run(environment.execute(OpenEnvironmentParams(clone_root=clone_root)))
        except ServerDidNotStartError as error:
            sys.stderr.write(f"slice-panel could not open the environment: {error}\n")

            return ExitCode.SERVER_UNREACHABLE
        except MountingFailedError as error:
            sys.stderr.write(f"slice-panel could not open the environment: {error}\n")

            return ExitCode.MOUNTING_FAILED

        return ExitCode.OK

    @staticmethod
    async def _answer_of(launcher: ProcessLauncher, argv: tuple[str, ...]) -> str:
        outcome = await launcher.ran(argv)
        if outcome.exit_code != 0 or not outcome.stdout.strip():
            raise OSError(f"`{' '.join(argv)}` said: {outcome.stderr or 'nothing'}")

        return outcome.stdout.strip()
