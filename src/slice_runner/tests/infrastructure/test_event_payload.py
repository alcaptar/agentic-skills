from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

import pytest

from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.exceptions import UnreadableEventLogError
from slice_runner.domain.run_state import RunState
from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.tests.mothers.event_mother import EventMother
from slice_runner.tests.mothers.feature_slice_mother import FeatureSliceMother


class TestWhatTheProgramEmits:
    def test_the_event_serialises_with_the_repo_the_issue_the_slice_the_step_the_instant_the_spend_and_the_status(
        self,
    ) -> None:
        assert EventPayload.from_domain(EventMother.advancing()).to_contract() == {
            "slice_id": "slice-05",
            "repo": EventMother.REPO,
            "issue": EventMother.ISSUE,
            "step": "run-controls",
            "ts": "2024-01-01T12:30:45+00:00",
            "spend": {
                "cost_usd": 0.3433209,
                "turns": 9,
                "duration_ms": 36315,
                "calls": 1,
                "models": ["claude-sonnet-5"],
                "input_tokens": 13,
                "output_tokens": 1159,
                "cache_creation_tokens": 42251,
                "cache_read_tokens": 241303,
                "ttft_ms": 5588,
                "duration_api_ms": 32189,
            },
            "status": "advancing",
            "parent": FeatureSliceMother.PARENT,
            "name": FeatureSliceMother.NAME,
        }

    def test_a_closing_event_writes_the_state_it_closed_with_under_closed_as(self) -> None:
        merged = EventPayload.from_domain(EventMother.closed()).to_contract()
        blocked = EventPayload.from_domain(EventMother.blocked_by_the_judge()).to_contract()

        assert (merged["status"], merged["closed_as"]) == ("closed", "merged")
        assert (blocked["status"], blocked["closed_as"]) == ("closed", "blocked-verify")

    def test_an_event_that_does_not_close_leaves_the_key_out_instead_of_emitting_null(self) -> None:
        assert "closed_as" not in EventPayload.from_domain(EventMother.advancing()).to_contract()


class TestWhatTheProgramReads:
    _ROW_OF_TODAY: ClassVar[dict[str, object]] = {
        "slice_id": "slice-05",
        "repo": EventMother.REPO,
        "issue": EventMother.ISSUE,
        "step": "await-merge",
        "ts": "2024-01-01T12:31:15+00:00",
        "spend": {
            "cost_usd": 0.0512,
            "turns": 3,
            "duration_ms": 1000,
            "calls": 1,
            "models": ["claude-sonnet-5"],
            "input_tokens": 1,
            "output_tokens": 1,
            "cache_creation_tokens": 1,
            "cache_read_tokens": 1,
            "ttft_ms": 1,
            "duration_api_ms": 1,
        },
        "status": "closed",
    }

    def test_a_closing_row_written_before_the_closing_state_existed_is_still_read(self) -> None:
        event = EventPayload.from_dict(dict(self._ROW_OF_TODAY)).to_domain()

        assert (event.status, event.closure) == (EventStatus.CLOSED, Closure.open())

    def test_a_closing_row_reads_back_with_the_state_it_closed_with(self) -> None:
        row = EventPayload.from_domain(EventMother.blocked_by_the_judge()).to_contract()

        assert EventPayload.from_dict(row).to_domain() == EventMother.blocked_by_the_judge()

    def test_a_row_written_before_the_feature_was_recorded_is_still_read_without_it(self) -> None:
        event = EventPayload.from_dict(dict(self._ROW_OF_TODAY)).to_domain()

        assert event.feature_slice is None

    def test_a_row_with_the_parent_and_the_name_reads_back_with_the_feature_it_belongs_to(self) -> None:
        row = EventPayload.from_domain(EventMother.advancing()).to_contract()

        assert EventPayload.from_dict(row).to_domain().feature_slice == FeatureSliceMother.of_the_feature()

    def test_an_event_without_the_feature_writes_neither_key(self) -> None:
        row = EventPayload.from_domain(EventMother.advancing_before_the_feature_was_recorded()).to_contract()

        assert "parent" not in row
        assert "name" not in row

    def test_a_row_with_the_pending_status_reads_as_a_pending_event(self) -> None:
        row = EventPayload.from_domain(EventMother.pending()).to_contract()

        assert row["status"] == "pending"
        assert EventPayload.from_dict(row).to_domain().status is EventStatus.PENDING


class TestReadingTheClosedAsOfEveryRowOfTheLog:
    @pytest.mark.parametrize(
        ("closed_as", "state", "reason"),
        [
            ("merged", RunState.MERGED, None),
            ("blocked-controls", RunState.BLOCKED, ClosingReason.CONTROLS),
            ("blocked-hygiene", RunState.BLOCKED, ClosingReason.CONTROLS),
            ("blocked-verify", RunState.BLOCKED, ClosingReason.JUDGE),
            ("blocked-unchanged-diff", RunState.BLOCKED, ClosingReason.JUDGE),
            ("blocked-ci-red", RunState.BLOCKED, ClosingReason.CI_RED),
            ("blocked-ci-indeterminate", RunState.BLOCKED, ClosingReason.CI_INDETERMINATE),
            ("blocked-ci-conflict", RunState.BLOCKED, ClosingReason.CI_CONFLICT),
            ("blocked-worktree", RunState.BLOCKED, ClosingReason.WORKTREE),
            ("blocked-leftover-worktree", RunState.BLOCKED, ClosingReason.WORKTREE),
            ("aborted-budget", RunState.ABORTED, ClosingReason.BUDGET),
            ("aborted-unmeasured-call", RunState.ABORTED, ClosingReason.UNMEASURED_CALL),
        ],
    )
    def test_the_value_of_every_generation_reads_as_a_state_and_its_reason(
        self, closed_as: str, state: RunState, reason: ClosingReason | None
    ) -> None:
        row = {**TestWhatTheProgramReads._ROW_OF_TODAY, "closed_as": closed_as}

        event = EventPayload.from_dict(row).to_domain()

        assert event.closure == Closure(state=state, reason=reason)

    def test_a_row_with_a_value_nobody_wrote_still_breaks_the_reading(self) -> None:
        row = {**TestWhatTheProgramReads._ROW_OF_TODAY, "closed_as": "blocked-nothing"}

        with pytest.raises(UnreadableEventLogError):
            EventPayload.from_dict(row)

    @pytest.mark.parametrize(
        ("reason", "closed_as"),
        [
            (ClosingReason.CONTROLS, "blocked-controls"),
            (ClosingReason.JUDGE, "blocked-verify"),
            (ClosingReason.CI_RED, "blocked-ci-red"),
            (ClosingReason.CI_INDETERMINATE, "blocked-ci-indeterminate"),
            (ClosingReason.CI_CONFLICT, "blocked-ci-conflict"),
            (ClosingReason.WORKTREE, "blocked-worktree"),
            (ClosingReason.BUDGET, "aborted-budget"),
            (ClosingReason.UNMEASURED_CALL, "aborted-unmeasured-call"),
        ],
    )
    def test_every_closure_is_written_with_the_value_of_the_majority_side_of_its_pair(
        self, reason: ClosingReason, closed_as: str
    ) -> None:
        closure = Closure.because_of(reason)
        event = replace(EventMother.closed(), closure=closure)

        written = EventPayload.from_domain(event).to_contract()

        assert written["closed_as"] == closed_as
