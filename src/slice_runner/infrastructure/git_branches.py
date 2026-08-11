from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.branches import Branches

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process, ProcessOutput


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

        raise self._failure(argv, output)

    def create(self, *, worktree: str, name: str, base: str) -> None:
        argv = ["git", "-C", worktree, "switch", "-c", name, base]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise self._failure(argv, output)

    def commits_behind_remote(self, *, worktree: str, base: str) -> int:
        self._fetch(worktree)
        argv = ["git", "-C", worktree, "rev-list", "--count", f"{base}..origin/{base}"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise self._failure(argv, output)

        return int(output.stdout.strip())

    def _fetch(self, worktree: str) -> None:
        argv = ["git", "-C", worktree, "fetch", "origin", "--quiet"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise self._failure(argv, output)

    @staticmethod
    def _failure(argv: list[str], output: ProcessOutput) -> GitCommandFailedError:
        return GitCommandFailedError(f"{' '.join(argv)}: {output.stderr.strip() or f'git exited {output.code}'}")
