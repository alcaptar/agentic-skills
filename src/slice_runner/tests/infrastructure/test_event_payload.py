from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.run_state import RunState
from slice_runner.infrastructure.event_payload import EventPayload
from slice_runner.tests.mothers.event_mother import EventMother


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

        assert (event.status, event.state) == (EventStatus.CLOSED, RunState.OPEN)

    def test_a_closing_row_reads_back_with_the_state_it_closed_with(self) -> None:
        row = EventPayload.from_domain(EventMother.blocked_by_the_judge()).to_contract()

        assert EventPayload.from_dict(row).to_domain() == EventMother.blocked_by_the_judge()
