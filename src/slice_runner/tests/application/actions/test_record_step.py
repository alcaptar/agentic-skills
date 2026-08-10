from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

from slice_runner.application.actions.record_step import RecordStep, RecordStepParams
from slice_runner.domain.clock import Clock
from slice_runner.domain.event_log import EventLog
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.domain.transition import Transition
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother

if TYPE_CHECKING:
    from slice_runner.domain.run import Run

_REPO = "alcaptar/agentic-skills"
_ISSUE = 150
_SLICE = "slice-07"
_AT = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)


class _Recorder:
    def __init__(self) -> None:
        self.repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        self.events: Mock = create_autospec(EventLog, spec_set=True, instance=True)
        self.clock: Mock = create_autospec(Clock, spec_set=True, instance=True)
        self.clock.now.return_value = _AT

    @property
    def action(self) -> RecordStep:
        return RecordStep(repository=self.repository, events=self.events, clock=self.clock)


class _Given:
    @staticmethod
    def params(
        *,
        current: Run,
        transition: Transition,
        label: IssueLabel | None = IssueLabel.IN_PROGRESS,
        spend: HarnessSpend | None = None,
    ) -> RecordStepParams:
        return RecordStepParams(
            repo=_REPO,
            issue=_ISSUE,
            slice_id=_SLICE,
            current=current,
            label=label,
            transition=transition,
            spend=spend if spend is not None else HarnessSpend.nothing(),
        )


class TestWhatItPersistsOfTheRun:
    def test_a_run_that_moved_is_written_so_the_next_invocation_resumes_where_this_one_left_it(self) -> None:
        recorder = _Recorder()
        current = RunMother.implementing()
        transition = Transition(run=RunMother.running_the_controls())

        recorder.action.execute(_Given.params(current=current, transition=transition))

        assert recorder.repository.write_run.call_args.kwargs["run"].step is Step.RUN_CONTROLS

    def test_a_run_that_did_not_move_is_not_written_so_a_tick_does_not_cost_a_write_on_the_issue(self) -> None:
        recorder = _Recorder()
        current = RunMother.awaiting_merge()
        transition = Transition(run=RunMother.awaiting_merge(), wait_seconds=30)

        recorder.action.execute(_Given.params(current=current, transition=transition))

        assert recorder.repository.write_run.call_count == 0

    def test_the_run_it_persists_carries_the_spend_accumulated_so_far_and_not_the_machine_one(self) -> None:
        recorder = _Recorder()
        spend = HarnessSpendMother.of_the_implementer_call()
        transition = Transition(run=RunMother.judging())

        result = recorder.action.execute(
            _Given.params(current=RunMother.implementing(), transition=transition, spend=spend)
        )

        assert result.run.spend == spend
        assert recorder.repository.write_run.call_args.kwargs["run"].spend == spend


class TestHowItMovesTheLabel:
    def test_the_label_of_the_new_state_replaces_the_one_the_slice_carried(self) -> None:
        recorder = _Recorder()
        transition = Transition(run=RunMother.awaiting_merge())

        result = recorder.action.execute(
            _Given.params(current=RunMother.implementing(), transition=transition, label=IssueLabel.IN_PROGRESS)
        )

        assert recorder.repository.write_label.call_args.kwargs["add"] is IssueLabel.AWAITING_MERGE
        assert recorder.repository.write_label.call_args.kwargs["remove"] is IssueLabel.IN_PROGRESS
        assert result.label is IssueLabel.AWAITING_MERGE

    def test_a_label_that_did_not_change_is_not_rewritten(self) -> None:
        recorder = _Recorder()
        transition = Transition(run=RunMother.running_the_controls())

        recorder.action.execute(
            _Given.params(current=RunMother.implementing(), transition=transition, label=IssueLabel.IN_PROGRESS)
        )

        assert recorder.repository.write_label.call_count == 0
        assert recorder.repository.remove_label.call_count == 0

    def test_a_closure_that_carries_no_label_retires_the_one_that_was_there(self) -> None:
        recorder = _Recorder()
        transition = Transition(run=RunMother.awaiting_merge(), state=RunState.MERGED)

        result = recorder.action.execute(
            _Given.params(current=RunMother.awaiting_merge(), transition=transition, label=IssueLabel.AWAITING_MERGE)
        )

        assert recorder.repository.remove_label.call_args.kwargs["remove"] is IssueLabel.AWAITING_MERGE
        assert result.label is None

    def test_a_closure_with_no_label_on_a_slice_that_had_none_does_not_ask_the_forum_to_retire_anything(self) -> None:
        recorder = _Recorder()
        transition = Transition(run=RunMother.awaiting_merge(), state=RunState.MERGED)

        recorder.action.execute(_Given.params(current=RunMother.awaiting_merge(), transition=transition, label=None))

        assert recorder.repository.remove_label.call_count == 0


class TestTheEventItEmits:
    def test_every_transition_emits_one_event_naming_the_step_the_run_moved_to(self) -> None:
        recorder = _Recorder()
        transition = Transition(run=RunMother.judging())

        recorder.action.execute(_Given.params(current=RunMother.implementing(), transition=transition))

        emitted = recorder.events.emit.call_args.args[0]
        assert emitted.step is Step.VERIFY
        assert emitted.slice_id == _SLICE
        assert emitted.at == _AT

    def test_a_closing_transition_is_emitted_as_closed_so_the_log_says_the_run_ended(self) -> None:
        recorder = _Recorder()
        transition = Transition(run=RunMother.awaiting_merge(), state=RunState.MERGED)

        recorder.action.execute(_Given.params(current=RunMother.awaiting_merge(), transition=transition))

        assert recorder.events.emit.call_args.args[0].status is EventStatus.CLOSED

    def test_the_event_carries_the_accumulated_spend_so_the_log_shows_what_the_run_costs_so_far(self) -> None:
        recorder = _Recorder()
        spend = HarnessSpendMother.of_the_implementer_call()
        transition = Transition(run=RunMother.judging())

        recorder.action.execute(_Given.params(current=RunMother.implementing(), transition=transition, spend=spend))

        assert recorder.events.emit.call_args.args[0].spend == spend

    def test_a_tick_that_writes_nothing_still_emits_its_event_so_a_wait_is_not_invisible(self) -> None:
        recorder = _Recorder()
        transition = Transition(run=RunMother.awaiting_merge(), wait_seconds=30)

        recorder.action.execute(_Given.params(current=RunMother.awaiting_merge(), transition=transition))

        assert recorder.repository.write_run.call_count == 0
        assert recorder.events.emit.call_count == 1
