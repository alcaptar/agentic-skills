from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.design_capture import DesignCapture
from slice_runner.domain.design_captures import DesignCaptures
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.missing_design_captures import MissingDesignCaptures
from slice_runner.infrastructure.process_design_capture_store import ProcessDesignCaptureStore
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.design import Design


class _CapturesDirectory:
    def __init__(self, worktree: Path) -> None:
        self.worktree = worktree
        self.path = worktree / DesignCapturesDirectory.NAME

    def holding(self, *names: str) -> _CapturesDirectory:
        self.path.mkdir(exist_ok=True)
        for name in names:
            (self.path / name).write_text("captured", encoding="utf-8")

        return self

    def with_manifest(self, text: str) -> _CapturesDirectory:
        self.path.mkdir(exist_ok=True)
        (self.path / DesignCapturesDirectory.MANIFEST).write_text(text, encoding="utf-8")

        return self

    def with_manifest_of(self, manifest: dict[str, object]) -> _CapturesDirectory:
        return self.with_manifest(json.dumps(manifest))

    def read(self, *designs: Design) -> DesignCaptures | MissingDesignCaptures:
        store = ProcessDesignCaptureStore(process=Real.process())

        return store.read(worktree=str(self.worktree), designs=designs or (DesignMother.board(), DesignMother.detail()))


@pytest.mark.integration
class TestClearingTheCapturesDirectory:
    def test_a_file_left_by_the_previous_round_does_not_survive(self, tmp_path: Path) -> None:
        captures = _CapturesDirectory(tmp_path).holding("tablero.html")

        ProcessDesignCaptureStore(process=Real.process()).clear(worktree=str(tmp_path))

        assert not (captures.path / "tablero.html").exists()

    def test_clearing_a_worktree_that_never_had_the_directory_is_not_an_error(self, tmp_path: Path) -> None:
        ProcessDesignCaptureStore(process=Real.process()).clear(worktree=str(tmp_path))

        assert not (tmp_path / DesignCapturesDirectory.NAME).exists()

    def test_the_rest_of_the_worktree_is_left_alone(self, tmp_path: Path) -> None:
        (tmp_path / "keep.txt").write_text("kept", encoding="utf-8")
        _CapturesDirectory(tmp_path).holding("tablero.html")

        ProcessDesignCaptureStore(process=Real.process()).clear(worktree=str(tmp_path))

        assert (tmp_path / "keep.txt").read_text(encoding="utf-8") == "kept"


@pytest.mark.integration
class TestReadingTheCapturesTheImplementerLeft:
    def test_a_manifest_of_two_captures_gives_both_with_the_absolute_path_of_each_file(self, tmp_path: Path) -> None:
        captures = (
            _CapturesDirectory(tmp_path)
            .holding("tablero.html", "detalle.html")
            .with_manifest_of(
                {
                    "captures": [
                        {"design": "tablero", "state": "a 80 columnas", "file": "tablero.html"},
                        {"design": "detalle", "state": "con un hallazgo", "file": "detalle.html"},
                    ]
                }
            )
        )

        read = captures.read()

        assert read == DesignCaptures(
            captures=(
                DesignCapture(design="tablero", state="a 80 columnas", path=str(captures.path / "tablero.html")),
                DesignCapture(design="detalle", state="con un hallazgo", path=str(captures.path / "detalle.html")),
            )
        )

    def test_an_unreadable_manifest_means_no_captures_and_says_why(self, tmp_path: Path) -> None:
        read = _CapturesDirectory(tmp_path).with_manifest("{not json").read()

        assert isinstance(read, MissingDesignCaptures)
        assert "not JSON" in read.reason

    def test_a_manifest_that_declares_the_captures_missing_carries_its_reason(self, tmp_path: Path) -> None:
        read = _CapturesDirectory(tmp_path).with_manifest_of({"missing": "no terminal here"}).read()

        assert read == MissingDesignCaptures(reason="no terminal here")

    def test_a_capture_of_a_design_the_slice_does_not_cite_means_no_captures_and_says_which(
        self, tmp_path: Path
    ) -> None:
        captures = (
            _CapturesDirectory(tmp_path)
            .holding("otro.html")
            .with_manifest_of({"captures": [{"design": "otro", "state": "x", "file": "otro.html"}]})
        )

        read = captures.read()

        assert isinstance(read, MissingDesignCaptures)
        assert "otro" in read.reason

    def test_a_capture_whose_file_does_not_exist_means_no_captures_and_says_which(self, tmp_path: Path) -> None:
        captures = _CapturesDirectory(tmp_path).with_manifest_of(
            {"captures": [{"design": "tablero", "state": "x", "file": "ghost.html"}]}
        )

        read = captures.read()

        assert isinstance(read, MissingDesignCaptures)
        assert "ghost.html" in read.reason

    def test_a_single_missing_file_discards_the_whole_manifest(self, tmp_path: Path) -> None:
        captures = (
            _CapturesDirectory(tmp_path)
            .holding("tablero.html")
            .with_manifest_of(
                {
                    "captures": [
                        {"design": "tablero", "state": "x", "file": "tablero.html"},
                        {"design": "detalle", "state": "y", "file": "ghost.html"},
                    ]
                }
            )
        )

        assert isinstance(captures.read(), MissingDesignCaptures)

    def test_no_manifest_at_all_means_no_captures_and_says_so(self, tmp_path: Path) -> None:
        read = _CapturesDirectory(tmp_path).read()

        assert isinstance(read, MissingDesignCaptures)
        assert DesignCapturesDirectory.MANIFEST in read.reason

    def test_a_manifest_listing_no_captures_means_no_captures(self, tmp_path: Path) -> None:
        read = _CapturesDirectory(tmp_path).with_manifest_of({"captures": []}).read()

        assert isinstance(read, MissingDesignCaptures)
