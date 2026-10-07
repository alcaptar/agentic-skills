from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

import pytest

from slice_panel.domain.call_budget import CallBudget
from slice_panel.domain.exceptions import ProcessTimedOutError
from slice_panel.infrastructure.subprocess_process_launcher import SubprocessProcessLauncher

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestTheRealLauncher:
    @staticmethod
    def launcher(seconds: float = 10.0) -> SubprocessProcessLauncher:
        return SubprocessProcessLauncher(budget=CallBudget(seconds_per_call=seconds))

    @staticmethod
    def python(code: str) -> tuple[str, ...]:
        return (sys.executable, "-c", code)

    async def test_it_returns_what_the_process_wrote_and_its_exit_code(self) -> None:
        outcome = await self.launcher().ran(self.python("print('out')"))

        assert (outcome.exit_code, outcome.stdout, outcome.stderr) == (0, "out\n", "")

    async def test_a_non_zero_exit_is_data_and_keeps_the_reason_the_process_wrote_on_standard_error(self) -> None:
        code = "import sys; sys.stderr.write('why it failed'); sys.exit(3)"

        outcome = await self.launcher().ran(self.python(code))

        assert (outcome.exit_code, outcome.stderr) == (3, "why it failed")

    async def test_it_runs_the_process_from_the_directory_it_is_given(self, tmp_path: Path) -> None:
        outcome = await self.launcher().ran(self.python("import os; print(os.getcwd())"), cwd=tmp_path)

        assert outcome.stdout.strip() == str(tmp_path.resolve())

    async def test_a_process_that_outlives_its_budget_is_killed_and_named_in_the_error(self) -> None:
        started = time.monotonic()

        with pytest.raises(ProcessTimedOutError) as raised:
            await self.launcher(0.3).ran(self.python("import time; print('half'); time.sleep(30)"))

        assert time.monotonic() - started < 10
        assert "time.sleep(30)" in str(raised.value)
        assert "did not finish" in str(raised.value)
