from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.branches import Branches

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class GitCommandFailedError(OSError):
    pass


class GitBranches(Branches):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def exists(self, *, worktree: str, name: str) -> bool:
        argv = ["git", "-C", worktree, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"]
        output = self._process.run(argv, stdin="")
        if output.code == 0:
            return True
        if output.code == 1:
            return False

        raise GitCommandFailedError(f"{' '.join(argv)}: {output.stderr.strip() or f'git exited {output.code}'}")
