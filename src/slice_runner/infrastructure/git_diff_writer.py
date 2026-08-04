from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.diff_on_disk import DiffOnDisk
from slice_runner.domain.diff_writer import DiffWriter
from slice_runner.domain.exceptions import EmptyIndexError, UnresolvableRepoOrBaseError

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.infrastructure.process import Process


class GitDiffWriter(DiffWriter):
    PATCH_NAME: ClassVar[str] = "slice.diff"

    def __init__(self, *, process: Process, destination: Path) -> None:
        self._process = process
        self._destination = destination

    def write(self, *, repo: str, base: str) -> DiffOnDisk:
        files = self._staged_names(repo=repo, base=base)
        if not files:
            raise EmptyIndexError(f"nothing staged against {base}: nothing to verify (forgotten git add?)")

        return DiffOnDisk(diff=self._written_patch(repo=repo, base=base), files=files)

    def _staged_names(self, *, repo: str, base: str) -> tuple[str, ...]:
        listing = self._diffed(repo=repo, base=base, extra=["--name-only"])

        return tuple(line for line in listing.splitlines() if line.strip())

    def _written_patch(self, *, repo: str, base: str) -> Path:
        self._destination.mkdir(parents=True, exist_ok=True)
        patch = self._destination / self.PATCH_NAME
        patch.write_text(self._diffed(repo=repo, base=base, extra=[]), encoding="utf-8")

        return patch

    def _diffed(self, *, repo: str, base: str, extra: list[str]) -> str:
        argv = ["git", "-C", repo, "diff", "--cached", *extra, "--merge-base", base]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise UnresolvableRepoOrBaseError(
                f"could not diff {repo!r} against {base!r}: {output.stderr.strip() or f'git exited {output.code}'}"
            )

        return output.stdout
