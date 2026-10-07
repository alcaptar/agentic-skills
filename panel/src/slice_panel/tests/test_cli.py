from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from slice_panel.infrastructure.cli import Cli
from slice_panel.infrastructure.exit_code import ExitCode
from slice_panel.infrastructure.herdr_tabs import HerdrFailedError
from slice_panel.infrastructure.panel_app import PanelApp
from slice_panel.tests.doubles import (
    AttachedToTheSessionError,
    FakeClock,
    RecordingLauncher,
    RecordingUnboundedProcesses,
)
from slice_panel.tests.mothers.herdr_mother import HerdrMother
from slice_panel.tests.mothers.outcome_mother import OutcomeMother

if TYPE_CHECKING:
    from slice_panel.domain.process_outcome import ProcessOutcome


class WithoutDrawing:
    @pytest.fixture(autouse=True)
    def never_draw(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse_to_draw(self: PanelApp) -> None:
            raise AssertionError("the panel was drawn without what herdr gives it")

        monkeypatch.setattr(PanelApp, "run", refuse_to_draw)


class TestWithoutHerdrInstalled(WithoutDrawing):
    @pytest.fixture(autouse=True)
    def no_herdr_on_the_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda name: None)

    def test_the_panel_says_it_needs_herdr_and_exits_non_zero_without_drawing_anything(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main()

        captured = capsys.readouterr()
        assert code != 0
        assert "herdr" in captured.err
        assert captured.out == ""


class WithHerdrOnThePath(WithoutDrawing):
    ROOT = ("git", "rev-parse", "--show-toplevel")
    REPO = ("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    STATUS = ("herdr", "status", "server")

    @pytest.fixture(autouse=True)
    def herdr_on_the_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/herdr")

    @staticmethod
    def run(launcher: RecordingLauncher, unbounded: RecordingUnboundedProcesses, clock: FakeClock | None = None) -> int:
        return Cli.run(launcher=launcher, unbounded=unbounded, clock=clock or FakeClock())

    @classmethod
    def mounting_answers(cls) -> dict[tuple[str, ...], ProcessOutcome]:
        return {
            cls.ROOT: OutcomeMother.succeeded("/work/clone\n"),
            cls.STATUS: HerdrMother.server_running(),
            ("herdr", "workspace", "list"): HerdrMother.workspace_list({}),
            ("herdr", "workspace", "create", "--cwd", "/work/clone", "--label", "clone", "--no-focus"): (
                HerdrMother.workspace_created()
            ),
            ("herdr", "agent", "start", "coordinador-clone", "--kind", "claude", "--pane", HerdrMother.PANE): (
                OutcomeMother.succeeded()
            ),
            ("herdr", "pane", "split", HerdrMother.PANE, "--direction", "right", "--no-focus"): (
                HerdrMother.pane_split("w1:p4")
            ),
            ("herdr", "pane", "run", "w1:p4", "slice-panel"): OutcomeMother.succeeded(),
            ("herdr", "workspace", "focus", HerdrMother.WORKSPACE): OutcomeMother.succeeded(),
        }


class TestWithoutAWorkspace(WithHerdrOnThePath):
    @pytest.fixture(autouse=True)
    def no_workspace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HERDR_WORKSPACE_ID", raising=False)

    def test_the_environment_is_mounted_with_the_whole_sequence_of_herdr_commands_in_order(self) -> None:
        launcher = RecordingLauncher(self.mounting_answers())
        unbounded = RecordingUnboundedProcesses()

        with pytest.raises(AttachedToTheSessionError):
            self.run(launcher, unbounded)

        assert launcher.calls == [
            self.ROOT,
            self.STATUS,
            ("herdr", "workspace", "list"),
            ("herdr", "workspace", "create", "--cwd", "/work/clone", "--label", "clone", "--no-focus"),
            ("herdr", "agent", "start", "coordinador-clone", "--kind", "claude", "--pane", HerdrMother.PANE),
            ("herdr", "pane", "split", HerdrMother.PANE, "--direction", "right", "--no-focus"),
            ("herdr", "pane", "run", "w1:p4", "slice-panel"),
            ("herdr", "workspace", "focus", HerdrMother.WORKSPACE),
        ]
        assert unbounded.detached == []
        assert unbounded.replacements == [("herdr",)]

    def test_an_empty_variable_is_the_same_as_a_missing_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERDR_WORKSPACE_ID", "")
        launcher = RecordingLauncher(self.mounting_answers())

        with pytest.raises(AttachedToTheSessionError):
            self.run(launcher, RecordingUnboundedProcesses())

        assert ("herdr", "workspace", "list") in launcher.calls

    def test_a_stopped_server_is_launched_detached_and_never_through_the_launcher_that_carries_the_limit(
        self,
    ) -> None:
        answers = {**self.mounting_answers(), self.STATUS: HerdrMother.server_stopped()}
        launcher = RecordingLauncher(answers)
        unbounded = RecordingUnboundedProcesses()

        self.run(launcher, unbounded)

        assert unbounded.detached == [("herdr", "server")]
        assert ("herdr", "server") not in launcher.calls

    def test_a_server_that_never_answers_exits_with_its_own_code_says_so_and_creates_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        answers = {**self.mounting_answers(), self.STATUS: HerdrMother.server_stopped()}
        launcher = RecordingLauncher(answers)
        clock = FakeClock()

        code = self.run(launcher, RecordingUnboundedProcesses(), clock)

        captured = capsys.readouterr()
        assert code == ExitCode.SERVER_UNREACHABLE
        assert "10" in captured.err
        assert captured.out == ""
        assert launcher.calls_to("herdr", "workspace") == []

    def test_a_herdr_command_that_fails_while_mounting_is_not_reported_as_an_unknown_clone(self) -> None:
        create = ("herdr", "workspace", "create", "--cwd", "/work/clone", "--label", "clone", "--no-focus")
        answers = {**self.mounting_answers(), create: OutcomeMother.failed("boom", exit_code=1)}

        with pytest.raises(HerdrFailedError):
            self.run(RecordingLauncher(answers), RecordingUnboundedProcesses())

    def test_a_step_that_fails_after_creating_the_workspace_closes_it_exits_with_its_own_code_and_says_which(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        split = ("herdr", "pane", "split", HerdrMother.PANE, "--direction", "right", "--no-focus")
        close = ("herdr", "workspace", "close", HerdrMother.WORKSPACE)
        answers = {
            **self.mounting_answers(),
            split: OutcomeMother.failed("split boom"),
            close: OutcomeMother.succeeded(),
        }
        launcher = RecordingLauncher(answers)
        unbounded = RecordingUnboundedProcesses()

        code = self.run(launcher, unbounded)

        captured = capsys.readouterr()
        assert code == ExitCode.MOUNTING_FAILED
        assert "split-pane" in captured.err
        assert "split boom" in captured.err
        assert captured.out == ""
        assert launcher.calls[-1] == close
        assert unbounded.replacements == []

    def test_a_failing_cleanup_exits_with_the_same_code_and_says_both_failures(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        split = ("herdr", "pane", "split", HerdrMother.PANE, "--direction", "right", "--no-focus")
        close = ("herdr", "workspace", "close", HerdrMother.WORKSPACE)
        answers = {
            **self.mounting_answers(),
            split: OutcomeMother.failed("split boom"),
            close: OutcomeMother.failed("close boom"),
        }

        code = self.run(RecordingLauncher(answers), RecordingUnboundedProcesses())

        captured = capsys.readouterr()
        assert code == ExitCode.MOUNTING_FAILED
        assert "split boom" in captured.err
        assert "close boom" in captured.err
        assert captured.out == ""

    def test_outside_a_clone_nothing_is_asked_of_herdr_and_the_exit_code_says_so(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        launcher = RecordingLauncher({self.ROOT: OutcomeMother.failed("not a git repository", exit_code=128)})
        unbounded = RecordingUnboundedProcesses()

        code = self.run(launcher, unbounded)

        assert code == ExitCode.CLONE_UNKNOWN
        assert launcher.calls == [self.ROOT]
        assert unbounded.detached == []
        assert unbounded.replacements == []
        assert "not a git repository" in capsys.readouterr().err


class TestInsideAHerdrWorkspace(WithHerdrOnThePath):
    @pytest.fixture(autouse=True)
    def inside_a_workspace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HERDR_WORKSPACE_ID", "w1")

    def test_the_panel_is_drawn_without_mounting_anything(self, monkeypatch: pytest.MonkeyPatch) -> None:
        drawn: list[PanelApp] = []

        def record_the_drawing(app: PanelApp) -> None:
            drawn.append(app)

        monkeypatch.setattr(PanelApp, "run", record_the_drawing)
        launcher = RecordingLauncher(
            {self.ROOT: OutcomeMother.succeeded("/work/clone\n"), self.REPO: OutcomeMother.succeeded("owner/repo\n")}
        )
        unbounded = RecordingUnboundedProcesses()

        code = self.run(launcher, unbounded)

        assert code == ExitCode.OK
        assert len(drawn) == 1
        assert launcher.calls == [self.ROOT, self.REPO]
        assert unbounded.detached == []
        assert unbounded.replacements == []


@pytest.mark.integration
class TestTheInstalledExecutableWithoutHerdr:
    def test_a_process_with_no_herdr_on_the_path_exits_non_zero_and_writes_nothing_on_standard_output(self) -> None:
        code = "import sys; from slice_panel.infrastructure.cli import Cli; sys.exit(Cli.main())"

        completed = subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "PATH": ""},
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

        assert completed.returncode != 0
        assert "herdr" in completed.stderr
        assert completed.stdout == ""
