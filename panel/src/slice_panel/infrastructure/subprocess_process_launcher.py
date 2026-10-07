from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from slice_panel.domain.exceptions import ProcessTimedOutError
from slice_panel.domain.process_launcher import ProcessLauncher
from slice_panel.domain.process_outcome import ProcessOutcome

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from slice_panel.domain.call_budget import CallBudget


class SubprocessProcessLauncher(ProcessLauncher):
    def __init__(self, *, budget: CallBudget) -> None:
        self._budget = budget

    async def ran(self, argv: Sequence[str], *, cwd: Path | None = None) -> ProcessOutcome:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._budget.seconds_per_call)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise ProcessTimedOutError(argv, self._budget.seconds_per_call) from None

        return ProcessOutcome(
            exit_code=process.returncode if process.returncode is not None else -1,
            stdout=stdout.decode("utf-8"),
            stderr=stderr.decode("utf-8").strip(),
        )
