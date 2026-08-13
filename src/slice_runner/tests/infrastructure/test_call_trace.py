from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.domain.clock import Clock
from slice_runner.domain.exceptions import UnreadableCallTraceError
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_config import ClaudeConfig
from slice_runner.infrastructure.harness_call_payload import HarnessCallPayload
from slice_runner.infrastructure.local_call_trace import LocalCallTrace
from slice_runner.tests.mothers.harness_call_mother import HarnessCallMother

if TYPE_CHECKING:
    from pathlib import Path

_STAMP = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC)


class WrittenTrace:
    @staticmethod
    def records_under(root: Path) -> list[dict[str, object]]:
        ledger = root / "slice-runner" / "log" / "calls.jsonl"

        return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]


class WithTheTraceOutOfTheRealHome:
    @pytest.fixture(autouse=True)
    def trace_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path))

    @staticmethod
    def frozen_at(stamp: datetime = _STAMP) -> Mock:
        clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        clock.now.return_value = stamp
        return clock


class TestWhatIsWrittenDownOfACall(WithTheTraceOutOfTheRealHome):
    def test_a_call_is_written_as_the_run_it_came_from_the_step_it_served_and_the_session_of_its_conversation(
        self, tmp_path: Path
    ) -> None:
        LocalCallTrace(clock=self.frozen_at()).record(HarnessCallMother.of_the_implementer())

        assert WrittenTrace.records_under(tmp_path) == [
            {
                "repo": HarnessCallMother.REPO,
                "issue": HarnessCallMother.ISSUE,
                "slice_id": HarnessCallMother.SLICE_ID,
                "step": "implement",
                "session": HarnessCallMother.SESSION_OF_THE_IMPLEMENTER,
                "ts": _STAMP.isoformat(),
            }
        ]


class TestTheTraceOnlyGrows(WithTheTraceOutOfTheRealHome):
    def test_the_two_calls_of_a_slice_are_both_kept_so_the_judge_does_not_overwrite_the_implementer(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())

        trace.record(HarnessCallMother.of_the_implementer())
        trace.record(HarnessCallMother.of_the_judge())

        assert [(record["step"], record["session"]) for record in WrittenTrace.records_under(tmp_path)] == [
            ("implement", HarnessCallMother.SESSION_OF_THE_IMPLEMENTER),
            ("verify", HarnessCallMother.SESSION_OF_THE_JUDGE),
        ]


class TestFindingTheSessionOfAPastCall(WithTheTraceOutOfTheRealHome):
    def test_the_session_of_the_call_that_served_that_run_and_step_is_returned(self, tmp_path: Path) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())

        found = trace.sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == (HarnessCallMother.SESSION_OF_THE_IMPLEMENTER,)

    def test_every_matching_call_is_returned_in_the_order_it_was_recorded_so_the_latest_retry_is_last(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())
        trace.record(HarnessCallMother.of_the_judge())
        trace.record(HarnessCallMother.of_the_implementer())

        found = trace.sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == (HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, HarnessCallMother.SESSION_OF_THE_IMPLEMENTER)

    def test_a_slice_and_step_never_recorded_returns_nothing_instead_of_guessing_a_session(
        self, tmp_path: Path
    ) -> None:
        LocalCallTrace(clock=self.frozen_at()).record(HarnessCallMother.of_the_implementer())

        found = LocalCallTrace(clock=self.frozen_at()).sessions_of(
            repo=HarnessCallMother.REPO, issue=HarnessCallMother.ISSUE, slice_id="slice-99", step=Step.VERIFY
        )

        assert found == ()

    def test_a_trace_never_written_returns_nothing_instead_of_failing(self, tmp_path: Path) -> None:
        found = LocalCallTrace(clock=self.frozen_at()).sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == ()

    def test_two_features_that_happen_to_share_a_slice_id_are_told_apart_by_their_repo_and_issue(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())
        other_feature = HarnessCallMother.of_the_implementer_of_another_feature()
        trace.record(other_feature)

        found = trace.sessions_of(
            repo=HarnessCallMother.OTHER_REPO,
            issue=HarnessCallMother.OTHER_ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == (other_feature.session,)

    def test_a_line_from_before_this_run_carried_identity_is_still_readable_and_never_matches_by_accident(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "log" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(
            json.dumps({"slice_id": HarnessCallMother.SLICE_ID, "step": "implement", "session": "old-session"}) + "\n",
            encoding="utf-8",
        )

        found = LocalCallTrace(clock=self.frozen_at()).sessions_of(
            repo=HarnessCallMother.REPO,
            issue=HarnessCallMother.ISSUE,
            slice_id=HarnessCallMother.SLICE_ID,
            step=Step.IMPLEMENT,
        )

        assert found == ()

    def test_a_line_that_is_not_json_is_refused_instead_of_being_skipped_in_silence(self, tmp_path: Path) -> None:
        ledger = tmp_path / "slice-runner" / "log" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text("not json\n", encoding="utf-8")

        with pytest.raises(UnreadableCallTraceError):
            LocalCallTrace(clock=self.frozen_at()).sessions_of(
                repo=HarnessCallMother.REPO,
                issue=HarnessCallMother.ISSUE,
                slice_id=HarnessCallMother.SLICE_ID,
                step=Step.IMPLEMENT,
            )

    def test_a_line_this_program_did_not_write_is_refused_instead_of_being_skipped_in_silence(
        self, tmp_path: Path
    ) -> None:
        ledger = tmp_path / "slice-runner" / "log" / "calls.jsonl"
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({"step": "implement"}) + "\n", encoding="utf-8")

        with pytest.raises(UnreadableCallTraceError):
            LocalCallTrace(clock=self.frozen_at()).sessions_of(
                repo=HarnessCallMother.REPO,
                issue=HarnessCallMother.ISSUE,
                slice_id=HarnessCallMother.SLICE_ID,
                step=Step.IMPLEMENT,
            )


class TestFindingTheCallsOfAPastSlice(WithTheTraceOutOfTheRealHome):
    def test_every_call_of_the_slice_across_every_step_is_returned_in_the_order_it_was_recorded(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())
        trace.record(HarnessCallMother.of_the_judge())

        found = trace.calls_of(
            repo=HarnessCallMother.REPO, issue=HarnessCallMother.ISSUE, slice_id=HarnessCallMother.SLICE_ID
        )

        assert [(call.step, call.session) for call in found] == [
            (Step.IMPLEMENT, HarnessCallMother.SESSION_OF_THE_IMPLEMENTER),
            (Step.VERIFY, HarnessCallMother.SESSION_OF_THE_JUDGE),
        ]

    def test_a_slice_never_recorded_returns_nothing_instead_of_guessing_a_call(self, tmp_path: Path) -> None:
        found = LocalCallTrace(clock=self.frozen_at()).calls_of(
            repo=HarnessCallMother.REPO, issue=HarnessCallMother.ISSUE, slice_id=HarnessCallMother.SLICE_ID
        )

        assert found == ()

    def test_two_features_that_happen_to_share_a_slice_id_are_told_apart_by_their_repo_and_issue(
        self, tmp_path: Path
    ) -> None:
        trace = LocalCallTrace(clock=self.frozen_at())
        trace.record(HarnessCallMother.of_the_implementer())
        other_feature = HarnessCallMother.of_the_implementer_of_another_feature()
        trace.record(other_feature)

        found = trace.calls_of(
            repo=HarnessCallMother.OTHER_REPO, issue=HarnessCallMother.OTHER_ISSUE, slice_id=HarnessCallMother.SLICE_ID
        )

        assert [call.session for call in found] == [other_feature.session]


class TestReadingBackWhatWasWritten:
    def test_a_line_written_by_this_program_is_read_back_as_the_same_call(self) -> None:
        written = HarnessCallPayload.from_call(HarnessCallMother.of_the_judge(), ts=_STAMP.isoformat())

        read_back = HarnessCallPayload.from_dict(written.to_contract())

        assert read_back == written


class TestWhereTheTraceLives:
    def test_the_directory_is_created_when_it_is_not_there_so_the_first_call_is_not_lost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ClaudeConfig.VARIABLE, str(tmp_path / "never-used-before"))

        LocalCallTrace(clock=WithTheTraceOutOfTheRealHome.frozen_at()).record(HarnessCallMother.of_the_judge())

        assert (tmp_path / "never-used-before" / "slice-runner" / "log" / "calls.jsonl").exists()
