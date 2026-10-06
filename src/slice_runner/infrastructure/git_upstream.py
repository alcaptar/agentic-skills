from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import UnreachableUpstreamError
from slice_runner.domain.upstream import Upstream
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessTimedOutError

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.infrastructure.process import Process, ProcessOutput


class GitUpstream(Upstream):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def commits_behind(self, *, checkout: Path) -> int:
        self._ran(["git", "-C", str(checkout), "fetch", "--quiet"])
        counted = self._ran(["git", "-C", str(checkout), "rev-list", "--count", "HEAD..@{upstream}"])

        return int(counted.stdout.strip())

    def _ran(self, argv: list[str]) -> ProcessOutput:
        try:
            output = self._process.run(argv, stdin="")
        except (ProcessTimedOutError, ProcessNotRunnableError) as error:
            raise UnreachableUpstreamError(f"{' '.join(argv)}: {error}") from error
        if output.code != 0:
            raise UnreachableUpstreamError(output.reason(tool=argv[0]))

        return output
