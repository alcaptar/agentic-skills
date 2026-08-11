from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessTimedOutError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestLocalProcess:
    _NOT_INSTALLED = "slice-runner-executable-that-is-not-installed"

    def test_an_executable_that_is_not_in_the_path_is_reported_as_the_environment_failure_it_is(self) -> None:
        with pytest.raises(ProcessNotRunnableError, match=self._NOT_INSTALLED):
            self._capped().run([self._NOT_INSTALLED], stdin="")

    def test_an_executable_that_runs_returns_its_code_and_both_streams(self) -> None:
        output = self._capped().run(["sh", "-c", "cat; printf oops >&2; exit 7"], stdin="hello")

        assert (output.code, output.stdout, output.stderr) == (7, "hello", "oops")

    def test_a_cwd_asked_for_becomes_the_working_directory_the_command_actually_runs_in(self, tmp_path: Path) -> None:
        output = self._capped().run(["pwd"], stdin="", cwd=str(tmp_path))

        assert output.stdout.strip() == str(tmp_path.resolve())

    @staticmethod
    def _capped() -> LocalProcess:
        return LocalProcess(budgets=Budgets())


@pytest.mark.integration
class TestACallThatDoesNotComeBack:
    def test_a_command_that_outlives_the_cap_of_the_budget_is_killed_and_reported_with_that_cap(self) -> None:
        capped = LocalProcess(budgets=Budgets(process_timeout_seconds=1))

        with pytest.raises(ProcessTimedOutError, match="sleep: killed after 1s"):
            capped.run(["sleep", "30"], stdin="")


@pytest.mark.integration
class TestABackgroundCallThatLeavesNoOutcome:
    def test_a_launch_that_dies_of_neither_a_timeout_nor_an_os_error_is_reported_as_a_process_failure(self) -> None:
        with pytest.raises(ProcessNotRunnableError, match="left neither a result nor a known error"):
            LocalProcess(budgets=Budgets()).run([], stdin="", on_line=lambda _: None)


@pytest.mark.integration
class TestACallThatWantsEachLineAsItArrives:
    _SPACED_LINES = "echo one; sleep 0.3; echo two; sleep 0.3; echo three"

    def test_every_line_the_command_prints_reaches_the_callback_in_order(self) -> None:
        seen: list[str] = []

        LocalProcess(budgets=Budgets()).run(["sh", "-c", self._SPACED_LINES], stdin="", on_line=seen.append)

        assert seen == ["one", "two", "three"]

    def test_the_callback_fires_while_the_command_is_still_running_and_not_only_once_it_exits(self) -> None:
        seen_at: list[float] = []

        LocalProcess(budgets=Budgets()).run(
            ["sh", "-c", self._SPACED_LINES], stdin="", on_line=lambda _: seen_at.append(time.monotonic())
        )

        assert seen_at[-1] - seen_at[0] > 0.5

    def test_the_full_output_still_comes_back_whole_once_the_command_is_done(self) -> None:
        output = LocalProcess(budgets=Budgets()).run(["sh", "-c", self._SPACED_LINES], stdin="", on_line=lambda _: None)

        assert output.stdout == "one\ntwo\nthree\n"

    def test_a_command_that_outlives_the_cap_is_killed_even_while_a_callback_is_watching_its_lines(self) -> None:
        capped = LocalProcess(budgets=Budgets(process_timeout_seconds=1))

        with pytest.raises(ProcessTimedOutError, match="sh: killed after 1s"):
            capped.run(["sh", "-c", "echo one; sleep 30"], stdin="", on_line=lambda _: None)

    def test_without_a_callback_the_process_behaves_exactly_as_before(self) -> None:
        output = LocalProcess(budgets=Budgets()).run(["sh", "-c", self._SPACED_LINES], stdin="")

        assert output.stdout == "one\ntwo\nthree\n"
