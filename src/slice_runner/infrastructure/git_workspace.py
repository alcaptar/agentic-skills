from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.workspace import Workspace
from slice_runner.infrastructure.git_branches import GitCommandFailedError

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class GitWorkspace(Workspace):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def stage(self, *, worktree: str, paths: tuple[str, ...]) -> None:
        already_gone = self._deletions_already_staged(worktree)
        pending = tuple(path for path in paths if path not in already_gone)
        if not pending:
            return

        self._git(worktree, "add", "--", *pending)

    def _deletions_already_staged(self, worktree: str) -> frozenset[str]:
        listing = self._git(worktree, "diff", "--cached", "--name-only", "--diff-filter=D")

        return frozenset(line for line in listing.splitlines() if line.strip())

    def staged(self, *, worktree: str) -> tuple[str, ...]:
        listing = self._git(worktree, "diff", "--cached", "--name-only")

        return tuple(line for line in listing.splitlines() if line.strip())

    def current_branch(self, *, worktree: str) -> str:
        return self._git(worktree, "symbolic-ref", "--short", "HEAD").strip()

    def commit(self, *, worktree: str, message: str) -> None:
        self._git(worktree, "commit", "-m", message)

    def push(self, *, worktree: str, branch: str) -> None:
        self._git(worktree, "push", "-u", "origin", branch)

    def _git(self, worktree: str, *args: str) -> str:
        argv = ["git", "-C", worktree, *args]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError(f"{' '.join(argv)}: {self._reason(output.stderr, output.stdout, output.code)}")

        return output.stdout

    @staticmethod
    def _reason(stderr: str, stdout: str, code: int) -> str:
        return stderr.strip() or stdout.strip() or f"git exited {code}"
