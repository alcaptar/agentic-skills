from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import UnreadableCallTraceError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload
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


class TestFindingTheSessionOfAPastCall(WithTheTraceOutOfTheRealHome):
    def test_the_session_of_the_call_that_served_that_slice_and_step_is_returned(self, tmp_path: Path) -> None:
        trace = LocalCallTrace()
        trace.record(HarnessCallMother.of_the_implementer())

        found = trace.sessions_of(slice_id=HarnessCallMother.SLICE_ID, step=Step.IMPLEMENT)

        assert found == (HarnessCallMother.SESSION_OF_THE_IMPLEMENTER,)

    def test_every_matching_call_is_returned_in_the_order_it_was_recorded_so_the_latest_retry_is_last(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace()
        trace.record(HarnessCallMother.of_the_implementer())
        trace.record(HarnessCallMother.of_the_judge())
        trace.record(HarnessCallMother.of_the_implementer())

        found = trace.sessions_of(slice_id=HarnessCallMother.SLICE_ID, step=Step.IMPLEMENT)

        assert found == (HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, HarnessCallMother.SESSION_OF_THE_IMPLEMENTER)

    def test_a_slice_and_step_never_recorded_returns_nothing_instead_of_guessing_a_session(
        self, tmp_path: Path
    ) -> None:
        LocalCallTrace().record(HarnessCallMother.of_the_implementer())

        found = LocalCallTrace().sessions_of(slice_id="slice-99", step=Step.VERIFY)

        assert found == ()

    def test_a_trace_never_written_returns_nothing_instead_of_failing(self, tmp_path: Path) -> None:
        assert LocalCallTrace().sessions_of(slice_id=HarnessCallMother.SLICE_ID, step=Step.IMPLEMENT) == ()

    def test_a_line_that_is_not_json_is_refused_instead_of_being_skipped_in_silence(self, tmp_path: Path) -> None:
        ledger = tmp_path / "slice-runner" / "trace" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("not json\n", encoding="utf-8")

        with pytest.raises(UnreadableCallTraceError):
            LocalCallTrace().sessions_of(slice_id=HarnessCallMother.SLICE_ID, step=Step.IMPLEMENT)

    def test_a_line_this_program_did_not_write_is_refused_instead_of_being_skipped_in_silence(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "trace" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({"step": "implement"}) + "\n", encoding="utf-8")

        with pytest.raises(UnreadableCallTraceError):
            LocalCallTrace().sessions_of(slice_id=HarnessCallMother.SLICE_ID, step=Step.IMPLEMENT)


class TestReadingBackWhatWasWritten:
    def test_a_line_written_by_this_program_is_read_back_as_the_same_call(self) -> None:
        written = HarnessCallPayload.from_call(HarnessCallMother.of_the_judge())

        read_back = HarnessCallPayload.from_dict(written.to_contract())

        assert read_back == written


class TestWhereTheTraceLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_call_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalCallTrace().record(HarnessCallMother.of_the_judge())

        assert (tmp_path / "never-used-before" / "slice-runner" / "trace" / "calls.jsonl").exists()
