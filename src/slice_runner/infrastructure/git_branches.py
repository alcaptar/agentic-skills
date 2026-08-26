from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.branch_catch_up import BranchCatchUp
from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.branches import Branches
from slice_runner.domain.exceptions import UnresolvableBaseError
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


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

        raise GitCommandFailedError.from_command(argv, output)

    def create(self, *, worktree: str, name: str, base: str) -> None:
        self._fetch(worktree)
        argv = ["git", "-C", worktree, "switch", "-c", name, f"origin/{base}"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

    def commits_behind_remote(self, *, worktree: str, base: str) -> int:
        self._fetch(worktree)
        argv = ["git", "-C", worktree, "rev-list", "--count", f"{base}..origin/{base}"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise UnresolvableBaseError(f"{base} does not resolve against its remote: {output.reason(tool=argv[0])}")

        return int(output.stdout.strip())

    def catch_up(self, *, worktree: str, name: str, base: str) -> BranchCatchUp:
        self._fetch(worktree)
        for ref in (f"origin/{name}", f"origin/{base}"):
            if self._behind(worktree, ref):
                merging = self._merging(worktree, ref)
                if merging.outcome is BranchCatchUpOutcome.CONFLICTING:
                    return merging

        return BranchCatchUp.caught_up()

    def _behind(self, worktree: str, ref: str) -> bool:
        if not self._ref_exists(worktree, ref):
            return False

        argv = ["git", "-C", worktree, "rev-list", "--count", f"HEAD..{ref}"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

        return int(output.stdout.strip()) > 0

    def _ref_exists(self, worktree: str, ref: str) -> bool:
        argv = ["git", "-C", worktree, "rev-parse", "--verify", "--quiet", ref]
        output = self._process.run(argv, stdin="")
        if output.code == 0:
            return True
        if output.code == 1:
            return False

        raise GitCommandFailedError.from_command(argv, output)

    def conclude_merge(self, *, worktree: str) -> None:
        argv = ["git", "-C", worktree, "-c", "commit.gpgsign=false", "commit", "--no-edit"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

    def abort_merge(self, *, worktree: str) -> None:
        self._abort_merge(worktree)

    def changed_paths(self, *, worktree: str) -> tuple[str, ...]:
        cached = self._names(worktree, "diff", "--cached", "--name-only")
        unstaged = self._names(worktree, "diff", "--name-only")
        untracked = self._names(worktree, "ls-files", "--others", "--exclude-standard")

        return tuple(sorted({*cached, *unstaged, *untracked}))

    def _merging(self, worktree: str, ref: str) -> BranchCatchUp:
        dirty_before_merge = self.changed_paths(worktree=worktree)
        argv = ["git", "-C", worktree, "-c", "merge.ff=true", "-c", "commit.gpgsign=false", "merge", "--no-edit", ref]
        output = self._process.run(argv, stdin="")
        if output.code == 0:
            return BranchCatchUp.caught_up()
        if not self._merge_in_progress(worktree):
            raise GitCommandFailedError.from_command(argv, output)

        try:
            conflicting_paths = self._conflicting_paths(worktree)
        except Exception:
            self._abort_merge(worktree)
            raise

        return BranchCatchUp.conflicting(paths=conflicting_paths, dirty_before_merge=dirty_before_merge)

    def _conflicting_paths(self, worktree: str) -> tuple[str, ...]:
        argv = ["git", "-C", worktree, "-c", "core.quotePath=false", "diff", "--name-only", "--diff-filter=U"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

        return tuple(output.stdout.splitlines())

    def _names(self, worktree: str, *args: str) -> tuple[str, ...]:
        argv = ["git", "-C", worktree, *args]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

        return tuple(line for line in output.stdout.splitlines() if line.strip())

    def _merge_in_progress(self, worktree: str) -> bool:
        argv = ["git", "-C", worktree, "rev-parse", "--verify", "--quiet", "MERGE_HEAD"]
        output = self._process.run(argv, stdin="")

        return output.code == 0

    def _abort_merge(self, worktree: str) -> None:
        argv = ["git", "-C", worktree, "merge", "--abort"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)

    def _fetch(self, worktree: str) -> None:
        argv = ["git", "-C", worktree, "fetch", "origin", "--quiet"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GitCommandFailedError.from_command(argv, output)
