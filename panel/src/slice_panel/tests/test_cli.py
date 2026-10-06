from __future__ import annotations

import os
import subprocess
import sys

import pytest

from slice_panel.infrastructure.cli import Cli
from slice_panel.infrastructure.panel_app import PanelApp


class WithoutHerdr:
    @pytest.fixture(autouse=True)
    def no_herdr_on_the_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda name: None)

        def refuse_to_draw(self: PanelApp) -> None:
            raise AssertionError("the panel was drawn without herdr")

        monkeypatch.setattr(PanelApp, "run", refuse_to_draw)


class TestWithoutHerdrInstalled(WithoutHerdr):
    def test_the_panel_says_it_needs_herdr_and_exits_non_zero_without_drawing_anything(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = Cli.main()

        captured = capsys.readouterr()
        assert code != 0
        assert "herdr" in captured.err
        assert captured.out == ""


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
