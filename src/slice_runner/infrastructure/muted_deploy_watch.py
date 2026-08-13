from __future__ import annotations

from slice_runner.domain.deploy_watch import DeployWatch


class MutedDeployWatch(DeployWatch):
    def watch(self, *, worktree: str, repo: str, signal: str) -> None:
        return None
