from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import UnreadableProvenanceError
from slice_runner.domain.installed_code_match import InstalledCodeMatch
from slice_runner.infrastructure.diff_installed_code import DiffInstalledCode
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessOutput, ProcessTimedOutError
from slice_runner.infrastructure.uv_program_origin import UvProgramOrigin
from slice_runner.tests.doubles import RaisingOnCommand, ScriptedProcess
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path


class InstalledProgram:
    @staticmethod
    def install(tools_root: Path, *, checkout: Path, dist_info: str = "agentic_skills-0.0.0.dist-info") -> Path:
        site_packages = tools_root / UvProgramOrigin.TOOL / "lib" / "python3.11" / "site-packages"
        (site_packages / dist_info).mkdir(parents=True)
        (site_packages / dist_info / "direct_url.json").write_text(
            json.dumps({"url": f"file://{checkout}", "dir_info": {}}), encoding="utf-8"
        )
        (site_packages / "slice_runner").mkdir()

        return site_packages / "slice_runner"

    @staticmethod
    def source_of(checkout: Path) -> Path:
        source = checkout / "src" / "slice_runner"
        source.mkdir(parents=True)

        return source


class TestTheInstalledCodeComparedWithItsCheckout(InstalledProgram):
    @pytest.fixture(autouse=True)
    def tools_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setenv(UvProgramOrigin.VARIABLE, str(tmp_path / "uv-tools"))

        return tmp_path / "uv-tools"

    def test_a_checkout_that_is_not_on_disk_is_reported_gone_without_launching_anything(
        self, tools_root: Path, tmp_path: Path
    ) -> None:
        self.install(tools_root, checkout=tmp_path / "gone")
        process = ScriptedProcess()

        match = DiffInstalledCode(process=process).compared_with(checkout=tmp_path / "gone")

        assert match is InstalledCodeMatch.CHECKOUT_GONE
        assert process.calls == []

    def test_the_comparison_goes_through_the_process_port_with_both_source_trees(
        self, tools_root: Path, tmp_path: Path
    ) -> None:
        checkout = tmp_path / "clone"
        installed = self.install(tools_root, checkout=checkout)
        source = self.source_of(checkout)
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        DiffInstalledCode(process=process).compared_with(checkout=checkout)

        assert process.calls[0].argv == ["diff", "-rq", "-x", "__pycache__", str(installed), str(source)]

    def test_diff_exiting_one_means_the_code_differs(self, tools_root: Path, tmp_path: Path) -> None:
        checkout = tmp_path / "clone"
        self.install(tools_root, checkout=checkout)
        self.source_of(checkout)
        process = ScriptedProcess(ProcessOutput(code=1, stdout="Files a and b differ", stderr=""))

        match = DiffInstalledCode(process=process).compared_with(checkout=checkout)

        assert match is InstalledCodeMatch.DIFFERENT

    def test_diff_failing_for_any_other_reason_raises_with_what_it_said(self, tools_root: Path, tmp_path: Path) -> None:
        checkout = tmp_path / "clone"
        self.install(tools_root, checkout=checkout)
        self.source_of(checkout)
        process = ScriptedProcess(ProcessOutput(code=2, stdout="", stderr="diff: permission denied"))

        with pytest.raises(UnreadableProvenanceError, match="permission denied"):
            DiffInstalledCode(process=process).compared_with(checkout=checkout)

    @pytest.mark.parametrize("error", [ProcessTimedOutError("too slow"), ProcessNotRunnableError("no diff")])
    def test_a_diff_that_cannot_run_or_does_not_answer_raises_instead_of_escaping(
        self, tools_root: Path, tmp_path: Path, error: OSError
    ) -> None:
        checkout = tmp_path / "clone"
        self.install(tools_root, checkout=checkout)
        self.source_of(checkout)
        process = RaisingOnCommand(when=("diff",), raises=error)

        with pytest.raises(UnreadableProvenanceError):
            DiffInstalledCode(process=process).compared_with(checkout=checkout)


@pytest.mark.integration
class TestTheInstalledCodeComparedWithItsCheckoutForReal(InstalledProgram):
    @pytest.fixture(autouse=True)
    def tools_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setenv(UvProgramOrigin.VARIABLE, str(tmp_path / "uv-tools"))

        return tmp_path / "uv-tools"

    def test_the_same_code_is_the_same_even_with_other_versions_and_stale_bytecode(
        self, tools_root: Path, tmp_path: Path
    ) -> None:
        checkout = tmp_path / "clone"
        installed = self.install(tools_root, checkout=checkout, dist_info="agentic_skills-9.9.9.dist-info")
        source = self.source_of(checkout)
        (checkout / "pyproject.toml").write_text('version = "1.2.3"\n', encoding="utf-8")
        for tree in (installed, source):
            (tree / "cli.py").write_text("print('hi')\n", encoding="utf-8")
        (installed / "__pycache__").mkdir()
        (installed / "__pycache__" / "cli.pyc").write_bytes(b"compiled")

        match = DiffInstalledCode(process=Real.process()).compared_with(checkout=checkout)

        assert match is InstalledCodeMatch.SAME

    def test_a_file_changed_in_the_checkout_after_installing_makes_it_different(
        self, tools_root: Path, tmp_path: Path
    ) -> None:
        checkout = tmp_path / "clone"
        installed = self.install(tools_root, checkout=checkout)
        source = self.source_of(checkout)
        (installed / "cli.py").write_text("print('old')\n", encoding="utf-8")
        (source / "cli.py").write_text("print('new')\n", encoding="utf-8")

        match = DiffInstalledCode(process=Real.process()).compared_with(checkout=checkout)

        assert match is InstalledCodeMatch.DIFFERENT

    def test_a_file_added_in_the_checkout_after_installing_makes_it_different(
        self, tools_root: Path, tmp_path: Path
    ) -> None:
        checkout = tmp_path / "clone"
        self.install(tools_root, checkout=checkout)
        source = self.source_of(checkout)
        (source / "new_module.py").write_text("x = 1\n", encoding="utf-8")

        match = DiffInstalledCode(process=Real.process()).compared_with(checkout=checkout)

        assert match is InstalledCodeMatch.DIFFERENT
