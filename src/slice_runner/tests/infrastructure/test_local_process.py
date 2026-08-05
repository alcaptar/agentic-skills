from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.infrastructure.process import ProcessNotRunnableError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestLocalProcess:
    _NOT_INSTALLED = "slice-runner-executable-that-is-not-installed"

    def test_an_executable_that_is_not_in_the_path_is_reported_as_the_environment_failure_it_is(self) -> None:
        with pytest.raises(ProcessNotRunnableError, match=self._NOT_INSTALLED):
            LocalProcess().run([self._NOT_INSTALLED], stdin="")

    def test_an_executable_that_runs_returns_its_code_and_both_streams(self) -> None:
        output = LocalProcess().run(["sh", "-c", "cat; printf oops >&2; exit 7"], stdin="hello")

        assert (output.code, output.stdout, output.stderr) == (7, "hello", "oops")

    def test_a_cwd_asked_for_becomes_the_working_directory_the_command_actually_runs_in(self, tmp_path: Path) -> None:
        output = LocalProcess().run(["pwd"], stdin="", cwd=str(tmp_path))

        assert output.stdout.strip() == str(tmp_path.resolve())
