from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.control_outcome import ControlOutcome
from slice_runner.domain.control_runner import ControlRunner
from slice_runner.domain.control_status import ControlStatus
from slice_runner.infrastructure.process import ProcessNotRunnableError

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.control_command import ControlCommand
    from slice_runner.infrastructure.process import Process


class LocalControlRunner(ControlRunner):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def run(self, command: ControlCommand, *, repo: str, out: Path) -> ControlOutcome:
        try:
            output = self._process.run(["sh", "-c", command.command], stdin="", cwd=repo)
        except ProcessNotRunnableError:
            return ControlOutcome(status=ControlStatus.UNKNOWN)

        out.mkdir(parents=True, exist_ok=True)
        log = out / f"{command.name}.log"
        log.write_text(output.stdout + output.stderr, encoding="utf-8")

        return ControlOutcome(status=ControlStatus.GREEN if output.code == 0 else ControlStatus.RED, log=log)
