from __future__ import annotations

import ast
from typing import TYPE_CHECKING, ClassVar

from conftest import _ROOT

from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.issue_label import IssueLabel

if TYPE_CHECKING:
    from pathlib import Path


class PanelScan:
    PANEL: ClassVar[Path] = _ROOT / "panel"
    FORBIDDEN_TEXT: ClassVar[tuple[str, ...]] = ("events.jsonl", ".claude", "CLAUDE_CONFIG_DIR")
    FORBIDDEN_CALLS: ClassVar[frozenset[str]] = frozenset({"home", "expanduser"})

    @classmethod
    def modules(cls) -> list[Path]:
        return sorted(
            path
            for path in cls.PANEL.rglob("*.py")
            if not any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(cls.PANEL).parts)
        )

    @staticmethod
    def imports_the_program(source: str) -> bool:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import) and any(alias.name.split(".")[0] == "slice_runner" for alias in node.names):
                return True
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "slice_runner":
                return True

        return False

    @classmethod
    def reaches_the_files_of_the_program(cls, source: str) -> bool:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.startswith("~") or any(text in node.value for text in cls.FORBIDDEN_TEXT):
                    return True
            if isinstance(node, ast.Attribute) and node.attr in cls.FORBIDDEN_CALLS:
                return True
            if isinstance(node, ast.Name) and node.id in cls.FORBIDDEN_CALLS:
                return True

        return False

    @classmethod
    def production_modules(cls) -> list[Path]:
        return [path for path in cls.modules() if "tests" not in path.relative_to(cls.PANEL).parts]

    @staticmethod
    def composes_a_merge(source: str) -> bool:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if any("merge" in token.lower() for token in node.value.split()):
                    return True

        return False

    @staticmethod
    def vocabulary_of(source: str, class_name: str) -> set[str]:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return {
                    statement.value.value
                    for statement in node.body
                    if isinstance(statement, ast.Assign)
                    and isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str)
                }

        raise AssertionError(f"`{class_name}` is not declared in the source")


class TestThePanelScansFindTheModulesAndTripOnWhatTheyShould:
    def test_the_scan_finds_the_modules_of_the_panel_and_none_of_its_environment(self) -> None:
        names = {path.name for path in PanelScan.modules()}

        assert {"panel_app.py", "subprocess_follow_source.py", "event_status.py"} <= names
        assert not any(".venv" in str(path) for path in PanelScan.modules())

    def test_an_import_of_the_program_trips_the_scan_in_both_spellings(self) -> None:
        assert PanelScan.imports_the_program("import slice_runner.domain.step")
        assert PanelScan.imports_the_program("from slice_runner.domain import step")

    def test_an_import_of_anything_else_does_not_trip_it(self) -> None:
        assert not PanelScan.imports_the_program("import json\nfrom slice_panel.domain import follow_line")

    def test_a_literal_naming_the_event_log_trips_the_scan(self) -> None:
        assert PanelScan.reaches_the_files_of_the_program("open('events.jsonl')")

    def test_a_path_under_the_configuration_root_trips_the_scan(self) -> None:
        assert PanelScan.reaches_the_files_of_the_program("Path('/x/.claude/slice-runner/log')")

    def test_a_path_resolved_from_the_home_directory_trips_the_scan(self) -> None:
        assert PanelScan.reaches_the_files_of_the_program("from pathlib import Path\nPath.home()")
        assert PanelScan.reaches_the_files_of_the_program("import os\nos.path.expanduser('x')")
        assert PanelScan.reaches_the_files_of_the_program("Path('~/anything')")

    def test_the_name_of_the_executable_alone_does_not_trip_the_scan(self) -> None:
        assert not PanelScan.reaches_the_files_of_the_program("ARGV = ('slice-runner', 'follow', '--json')")


class TestThePanelIsAnExternalConsumer:
    def test_no_module_of_the_panel_imports_the_program(self) -> None:
        offenders = [
            str(path.relative_to(_ROOT))
            for path in PanelScan.modules()
            if PanelScan.imports_the_program(path.read_text(encoding="utf-8"))
        ]

        assert offenders == []

    def test_no_module_of_the_panel_reaches_the_files_the_program_writes(self) -> None:
        offenders = [
            str(path.relative_to(_ROOT))
            for path in PanelScan.modules()
            if PanelScan.reaches_the_files_of_the_program(path.read_text(encoding="utf-8"))
        ]

        assert offenders == []


class TestTheVocabularyOfStatusesTheCopyHasToKeep:
    def test_the_extraction_reads_the_values_of_a_class_in_a_synthetic_source(self) -> None:
        source = "class A:\n    ONE = 'one'\n    TWO = 'two'\n"

        assert PanelScan.vocabulary_of(source, "A") == {"one", "two"}

    def test_the_statuses_of_the_panel_are_the_ones_the_program_emits(self) -> None:
        source = (PanelScan.PANEL / "src" / "slice_panel" / "domain" / "event_status.py").read_text(encoding="utf-8")

        assert PanelScan.vocabulary_of(source, "EventStatus") == {status.value for status in EventStatus}


class TestThePanelNeverMerges:
    def test_a_constant_naming_a_merge_trips_the_scan(self) -> None:
        assert PanelScan.composes_a_merge("COMMAND = ('gh', 'pr', 'merge', '12')")
        assert PanelScan.composes_a_merge("COMMAND = 'gh pr merge 12 --squash'")
        assert PanelScan.composes_a_merge("FLAG = '--auto-merge'")

    def test_a_constant_that_names_no_merge_does_not_trip_it(self) -> None:
        assert not PanelScan.composes_a_merge("COMMAND = ('slice-runner', 'go', '--repo', 'org/repo')")

    def test_the_scan_reaches_the_modules_that_compose_commands(self) -> None:
        names = {path.name for path in PanelScan.production_modules()}

        assert {"slice_runner_commands.py", "herdr_tabs.py", "cli.py"} <= names
        assert "test_panel_app.py" not in names

    def test_no_production_module_of_the_panel_composes_a_merge(self) -> None:
        offenders = [
            str(path.relative_to(_ROOT))
            for path in PanelScan.production_modules()
            if PanelScan.composes_a_merge(path.read_text(encoding="utf-8"))
        ]

        assert offenders == []


class TestTheLabelTheCopyHasToKeep:
    def test_the_label_that_marks_a_slice_awaiting_alignment_is_the_one_the_program_writes(self) -> None:
        source = (PanelScan.PANEL / "src" / "slice_panel" / "domain" / "slice_label.py").read_text(encoding="utf-8")

        assert PanelScan.vocabulary_of(source, "SliceLabel") == {IssueLabel.AWAITING_ALIGNMENT.value}
