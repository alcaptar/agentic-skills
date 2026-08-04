from __future__ import annotations

import pytest

from slice_runner.infrastructure.process import LocalProcess, ProcessNotRunnableError


class TestLocalProcess:
    _NOT_INSTALLED = "slice-runner-executable-that-is-not-installed"

    def test_an_executable_that_is_not_in_the_path_is_reported_as_the_environment_failure_it_is(self) -> None:
        with pytest.raises(ProcessNotRunnableError, match=self._NOT_INSTALLED):
            LocalProcess().run([self._NOT_INSTALLED], stdin="")

    def test_an_executable_that_runs_returns_its_code_and_both_streams(self) -> None:
        output = LocalProcess().run(["sh", "-c", "cat; printf oops >&2; exit 7"], stdin="hello")

        assert (output.code, output.stdout, output.stderr) == (7, "hello", "oops")
