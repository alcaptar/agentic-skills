from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.diff_reader import DiffReader
from slice_runner.domain.exceptions import EmptyIndexError, UnresolvableRepoOrBaseError
from slice_runner.domain.slice_diff import SliceDiff

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class GitDiffReader(DiffReader):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def read(self, *, repo: str, base: str) -> SliceDiff:
        files = self._staged_names(repo=repo, base=base)
        if not files:
            raise EmptyIndexError(f"nothing staged against {base}: nothing to verify (forgotten git add?)")

        return SliceDiff(text=self._diffed(repo=repo, base=base, extra=[]), files=files)

    def _staged_names(self, *, repo: str, base: str) -> tuple[str, ...]:
        listing = self._diffed(repo=repo, base=base, extra=["--name-only"])

        return tuple(line for line in listing.splitlines() if line.strip())

    def _diffed(self, *, repo: str, base: str, extra: list[str]) -> str:
        argv = ["git", "-C", repo, "diff", "--cached", *extra, "--merge-base", base]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise UnresolvableRepoOrBaseError(
                f"could not diff {repo!r} against {base!r}: {output.stderr.strip() or f'git exited {output.code}'}"
            )

        return output.stdout
