from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from slice_runner.domain.ruling import Ruling
from slice_runner.infrastructure.local_control_runner import LocalControlRunner
from slice_runner.tests.doubles import ProcessDoubles
from slice_runner.tests.mothers.control_command_mother import ControlCommandMother

if TYPE_CHECKING:
    import pytest

_REPO = "/repos/project"


class TestHowTheCommandIsRun:
    def test_the_command_runs_as_a_shell_line_through_the_injected_process_with_the_repo_as_its_working_directory(
        self, tmp_path: Path
    ) -> None:
        process = ProcessDoubles.exiting(code=0)

        LocalControlRunner(process=process).run(ControlCommandMother.lint(), repo=_REPO, out=tmp_path)

        process.run.assert_called_once_with(["sh", "-c", ControlCommandMother.LINT_COMMAND], stdin="", cwd=_REPO)


class TestTheRulingComesFromTheExitCode:
    def test_a_zero_exit_code_is_the_passing_ruling(self, tmp_path: Path) -> None:
        process = ProcessDoubles.exiting(code=0)

        outcome = LocalControlRunner(process=process).run(ControlCommandMother.lint(), repo=_REPO, out=tmp_path)

        assert outcome.ruling is Ruling.PASS

    def test_a_nonzero_exit_code_is_the_failing_ruling(self, tmp_path: Path) -> None:
        process = ProcessDoubles.exiting(code=1)

        outcome = LocalControlRunner(process=process).run(ControlCommandMother.lint(), repo=_REPO, out=tmp_path)

        assert outcome.ruling is Ruling.FAIL


class TestWhereTheOutputEnds:
    def test_the_full_stdout_and_stderr_land_in_a_log_named_after_the_control_inside_out(self, tmp_path: Path) -> None:
        process = ProcessDoubles.exiting(stdout="output line\n", stderr="warning line\n")

        LocalControlRunner(process=process).run(ControlCommandMother.lint(), repo=_REPO, out=tmp_path)

        written = (tmp_path / f"{ControlCommandMother.LINT_NAME}.log").read_text(encoding="utf-8")
        assert written == "output line\nwarning line\n"

    def test_the_log_is_written_even_when_the_control_passes_not_only_on_failure(self, tmp_path: Path) -> None:
        process = ProcessDoubles.exiting(code=0, stdout="all good\n")

        LocalControlRunner(process=process).run(ControlCommandMother.lint(), repo=_REPO, out=tmp_path)

        assert (tmp_path / f"{ControlCommandMother.LINT_NAME}.log").exists()

    def test_the_outcome_carries_the_log_path_and_not_its_content(self, tmp_path: Path) -> None:
        process = ProcessDoubles.exiting(stdout="secret build output\n")

        outcome = LocalControlRunner(process=process).run(ControlCommandMother.lint(), repo=_REPO, out=tmp_path)

        assert outcome.log == tmp_path / f"{ControlCommandMother.LINT_NAME}.log"


class TestTheLogIsNeverReopened:
    def test_the_adapter_never_rereads_the_log_it_just_wrote_to_build_the_outcome(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        process = ProcessDoubles.exiting(stdout="ok\n")
        self._forbid_rereading(monkeypatch)

        outcome = LocalControlRunner(process=process).run(ControlCommandMother.lint(), repo=_REPO, out=tmp_path)

        assert outcome.ruling is Ruling.PASS

    @staticmethod
    def _forbid_rereading(monkeypatch: pytest.MonkeyPatch) -> None:
        def reread(self: Path, *args: object, **kwargs: object) -> str:
            raise AssertionError("the log must never be reread to build the outcome")

        monkeypatch.setattr(Path, "read_text", reread)
