from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.deploy_watch import DeployWatch
from slice_runner.infrastructure.deploy_watch_invocation import DeployWatchInvocation

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class ClaudeDeployWatch(DeployWatch):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def watch(self, *, worktree: str, repo: str, signal: str) -> None:
        invocation = DeployWatchInvocation(worktree=worktree, repo=repo, signal=signal)
        self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd)
