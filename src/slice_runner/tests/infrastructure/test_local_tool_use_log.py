from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.local_tool_use_log import LocalToolUseLog
from slice_runner.tests.mothers.harness_call_tool_use_mother import HarnessCallToolUseMother

if TYPE_CHECKING:
    from pathlib import Path


class WrittenToolUses:
    @staticmethod
    def records_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "trace" / "tool-uses.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class WithTheLogOutOfTheRealHome:
    @pytest.fixture(autouse=True)
    def log_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))


class TestWhatIsWrittenDownOfACall(WithTheLogOutOfTheRealHome):
    def test_a_call_is_written_as_the_slice_the_step_the_session_and_every_tool_use_it_made(
        self, tmp_path: Path
    ) -> None:
        LocalToolUseLog().record(HarnessCallToolUseMother.of_the_implementer())

        assert WrittenToolUses.records_under(tmp_path) == [
            {
                "slice_id": HarnessCallToolUseMother.SLICE_ID,
                "step": "implement",
                "session": HarnessCallToolUseMother.SESSION,
                "uses": [
                    {"turn": 1, "tool": "Read", "path": "src/x.py"},
                    {"turn": 2, "tool": "Bash"},
                ],
            }
        ]


class TestTheLogOnlyGrows(WithTheLogOutOfTheRealHome):
    def test_a_second_call_is_appended_instead_of_overwriting_the_first(self, tmp_path: Path) -> None:
        log = LocalToolUseLog()

        log.record(HarnessCallToolUseMother.of_the_implementer())
        log.record(HarnessCallToolUseMother.of_the_implementer())

        assert len(WrittenToolUses.records_under(tmp_path)) == 2


class TestWhereTheLogLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_call_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalToolUseLog().record(HarnessCallToolUseMother.of_the_implementer())

        assert (tmp_path / "never-used-before" / "slice-runner" / "trace" / "tool-uses.jsonl").exists()
