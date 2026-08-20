from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.branches import Branches
from slice_runner.domain.exceptions import UnresolvableBaseError

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
        self._fetch(worktree)
        argv = ["git", "-C", worktree, "switch", "-c", name, f"origin/{base}"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise self._failure(argv, output)

    def commits_behind_remote(self, *, worktree: str, base: str) -> int:
        self._fetch(worktree)
        argv = ["git", "-C", worktree, "rev-list", "--count", f"{base}..origin/{base}"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise UnresolvableBaseError(
                f"{base} does not resolve against its remote: {output.stderr.strip() or f'git exited {output.code}'}"
            )

        return int(output.stdout.strip())

    def catch_up(self, *, worktree: str, name: str, base: str) -> BranchCatchUpOutcome:
        self._fetch(worktree)
        for ref in (f"origin/{name}", f"origin/{base}"):
            if self._behind(worktree, ref) and not self._merged(worktree, ref):
                return BranchCatchUpOutcome.CONFLICTING

        return BranchCatchUpOutcome.CAUGHT_UP

    def _behind(self, worktree: str, ref: str) -> bool:
        if not self._ref_exists(worktree, ref):
            return False

        argv = ["git", "-C", worktree, "rev-list", "--count", f"HEAD..{ref}"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise self._failure(argv, output)

        return int(output.stdout.strip()) > 0

    def _ref_exists(self, worktree: str, ref: str) -> bool:
        argv = ["git", "-C", worktree, "rev-parse", "--verify", "--quiet", ref]
        output = self._process.run(argv, stdin="")
        if output.code == 0:
            return True
        if output.code == 1:
            return False

        raise self._failure(argv, output)

    def _merged(self, worktree: str, ref: str) -> bool:
        argv = ["git", "-C", worktree, "-c", "merge.ff=true", "-c", "commit.gpgsign=false", "merge", "--no-edit", ref]
        output = self._process.run(argv, stdin="")
        if output.code == 0:
            return True
        if not self._merge_in_progress(worktree):
            raise self._failure(argv, output)

        self._abort_merge(worktree)

        return False

    def _merge_in_progress(self, worktree: str) -> bool:
        argv = ["git", "-C", worktree, "rev-parse", "--verify", "--quiet", "MERGE_HEAD"]
        output = self._process.run(argv, stdin="")

        return output.code == 0

    def _abort_merge(self, worktree: str) -> None:
        argv = ["git", "-C", worktree, "merge", "--abort"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise self._failure(argv, output)

    def _fetch(self, worktree: str) -> None:
        argv = ["git", "-C", worktree, "fetch", "origin", "--quiet"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise self._failure(argv, output)

    @staticmethod
    def _failure(argv: list[str], output: ProcessOutput) -> GitCommandFailedError:
        return GitCommandFailedError(f"{' '.join(argv)}: {output.stderr.strip() or f'git exited {output.code}'}")
