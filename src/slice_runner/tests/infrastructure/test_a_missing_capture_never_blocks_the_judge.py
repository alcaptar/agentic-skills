from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.verify_slice import VerifySlice
from slice_runner.application.queries.read_design_captures import ReadDesignCaptures, ReadDesignCapturesParams
from slice_runner.domain.corpus import Corpus
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.diff_reader import DiffReader
from slice_runner.domain.skill_library import SkillLibrary
from slice_runner.infrastructure.claude_verifier import ClaudeVerifier
from slice_runner.infrastructure.process_design_capture_store import ProcessDesignCaptureStore
from slice_runner.tests.doubles import RecordedProcess, RecordedSourceReader
from slice_runner.tests.infrastructure.test_claude_verifier import Calling
from slice_runner.tests.mothers.design_mother import DesignMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother
from slice_runner.tests.mothers.verification_mother import (
    JudgeMother,
    SliceDiffMother,
    VerifySliceParamsMother,
)
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path

_NO_CAPTURES = "No hay capturas: "


@pytest.mark.integration
class TestAnUnusableCaptureNeverStopsTheJudge(Calling):
    @staticmethod
    def _verifying(worktree: Path) -> tuple[RecordedProcess, VerifySlice]:
        reader: Mock = create_autospec(DiffReader, spec_set=True, instance=True)
        reader.read.return_value = SliceDiffMother.of_the_slice()
        skills: Mock = create_autospec(SkillLibrary, spec_set=True, instance=True)
        skills.directories.return_value = ()
        process = RecordedProcess(HarnessEnvelopeMother.recorded())
        action = VerifySlice(
            reader=reader,
            verifier=ClaudeVerifier(calls=Calling._calls(process), reader=RecordedSourceReader()),
            judge=JudgeMother.adversarial(),
            skills=skills,
            corpus=create_autospec(Corpus, spec_set=True, instance=True),
        )

        return process, action

    def _judged_with(self, worktree: Path, *, manifest: str | None, files: tuple[str, ...] = ()) -> str:
        directory = worktree / DesignCapturesDirectory.NAME
        directory.mkdir()
        for name in files:
            (directory / name).write_text("captured", encoding="utf-8")
        if manifest is not None:
            (directory / DesignCapturesDirectory.MANIFEST).write_text(manifest, encoding="utf-8")
        process, action = self._verifying(worktree)
        designs = (DesignMother.board(),)
        captures = ReadDesignCaptures(captures=ProcessDesignCaptureStore(process=Real.process())).execute(
            ReadDesignCapturesParams(worktree=str(worktree), designs=designs)
        )
        params = replace(
            VerifySliceParamsMother.against_the_base(), worktree=str(worktree), designs=designs, captures=captures
        )

        action.execute(params)

        assert process.calls == 1
        return process.stdin

    def test_an_unreadable_manifest_reaches_the_judge_as_no_captures_with_its_reason(self, tmp_path: Path) -> None:
        prompt = self._judged_with(tmp_path, manifest="{not json")

        assert f"{_NO_CAPTURES}the design captures manifest is not JSON" in prompt

    def test_a_manifest_declaring_the_captures_missing_reaches_the_judge_with_its_reason(self, tmp_path: Path) -> None:
        prompt = self._judged_with(tmp_path, manifest=json.dumps({"missing": "no terminal available"}))

        assert f"{_NO_CAPTURES}no terminal available" in prompt

    def test_a_capture_of_a_design_the_slice_does_not_cite_reaches_the_judge_as_no_captures(
        self, tmp_path: Path
    ) -> None:
        manifest = json.dumps({"captures": [{"design": "otro", "state": "x", "file": "otro.png"}]})

        prompt = self._judged_with(tmp_path, manifest=manifest, files=("otro.png",))

        assert f"{_NO_CAPTURES}the manifest has a capture of the design 'otro'" in prompt

    def test_a_capture_whose_file_does_not_exist_reaches_the_judge_as_no_captures(self, tmp_path: Path) -> None:
        manifest = json.dumps({"captures": [{"design": "tablero", "state": "x", "file": "ghost.png"}]})

        prompt = self._judged_with(tmp_path, manifest=manifest)

        assert f"{_NO_CAPTURES}the capture file ghost.png does not exist" in prompt
