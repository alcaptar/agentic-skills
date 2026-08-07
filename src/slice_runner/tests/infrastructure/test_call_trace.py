from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.local_call_trace import LocalCallTrace
from slice_runner.tests.mothers.harness_call_mother import HarnessCallMother

if TYPE_CHECKING:
    from pathlib import Path


class WrittenTrace:
    @staticmethod
    def records_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "trace" / "calls.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class WithTheTraceOutOfTheRealHome:
    @pytest.fixture(autouse=True)
    def trace_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))


class TestWhatIsWrittenDownOfACall(WithTheTraceOutOfTheRealHome):
    def test_a_call_is_written_as_the_slice_the_step_it_served_and_the_session_of_its_conversation(
        self, tmp_path: Path
    ) -> None:
        LocalCallTrace().record(HarnessCallMother.of_the_implementer())

        assert WrittenTrace.records_under(tmp_path) == [
            {
                "slice_id": HarnessCallMother.SLICE_ID,
                "step": "implement",
                "session": HarnessCallMother.SESSION_OF_THE_IMPLEMENTER,
            }
        ]


class TestTheTraceOnlyGrows(WithTheTraceOutOfTheRealHome):
    def test_the_two_calls_of_a_slice_are_both_kept_so_the_judge_does_not_overwrite_the_implementer(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace()

        trace.record(HarnessCallMother.of_the_implementer())
        trace.record(HarnessCallMother.of_the_judge())

        assert [(record["step"], record["session"]) for record in WrittenTrace.records_under(tmp_path)] == [
            ("implement", HarnessCallMother.SESSION_OF_THE_IMPLEMENTER),
            ("verify", HarnessCallMother.SESSION_OF_THE_JUDGE),
        ]


class TestWhereTheTraceLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_call_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalCallTrace().record(HarnessCallMother.of_the_judge())

        assert (tmp_path / "never-used-before" / "slice-runner" / "trace" / "calls.jsonl").exists()
