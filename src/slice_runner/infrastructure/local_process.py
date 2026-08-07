from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from slice_runner.infrastructure.process import Process, ProcessNotRunnableError, ProcessOutput, ProcessTimedOutError

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets


class LocalProcess(Process):
    def __init__(self, *, budgets: Budgets) -> None:
        self._budgets = budgets

    def run(self, argv: list[str], *, stdin: str, cwd: str | None = None) -> ProcessOutput:
        try:
            finished = subprocess.run(
                argv,
                input=stdin,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
                timeout=self._budgets.process_timeout_seconds,
            )
        except subprocess.TimeoutExpired as expired:
            raise ProcessTimedOutError(f"{argv[0]}: killed after {self._budgets.process_timeout_seconds}s") from expired
        except OSError as error:
            raise ProcessNotRunnableError(f"{argv[0]}: {error.strerror or error}") from error

        return ProcessOutput(code=finished.returncode, stdout=finished.stdout, stderr=finished.stderr)
