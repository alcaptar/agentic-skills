from __future__ import annotations

import os
import subprocess
import sys

import pytest

from slice_panel.infrastructure.cli import Cli
from slice_panel.infrastructure.exit_code import ExitCode
from slice_panel.infrastructure.panel_app import PanelApp


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


class TestWithoutAWorkspace(WithoutDrawing):
    @pytest.fixture(autouse=True)
    def herdr_on_the_path_but_no_workspace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/herdr")
        monkeypatch.delenv("HERDR_WORKSPACE_ID", raising=False)

    def test_the_panel_names_the_variable_and_exits_non_zero_without_drawing_anything(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main()

        captured = capsys.readouterr()
        assert code not in (0, ExitCode.HERDR_MISSING, ExitCode.CLONE_UNKNOWN)
        assert "HERDR_WORKSPACE_ID" in captured.err
        assert captured.out == ""

    def test_an_empty_variable_is_the_same_as_a_missing_one(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("HERDR_WORKSPACE_ID", "")

        code = Cli.main()

        assert code == ExitCode.WORKSPACE_UNKNOWN
        assert "HERDR_WORKSPACE_ID" in capsys.readouterr().err


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
