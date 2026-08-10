from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from slice_runner.application.actions.close_parent import CloseParentParams
from slice_runner.domain.alignment import Alignment
from slice_runner.domain.alignment_response import AlignmentResponse
from slice_runner.domain.alignment_response_kind import AlignmentResponseKind
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.exceptions import (
    DirtyIndexError,
    InvalidUnderstandingReportError,
    NoPullRequestError,
    NoSliceLeftError,
)
from slice_runner.domain.halt import Halt
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.domain.run import Run
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.tests.conductor import Conductor
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.rejection_mother import RejectionMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.select_slice_result_mother import SelectSliceResultMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, VerdictMother
from slice_runner.tests.mothers.verification_mother import VerificationMother

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.sub_issue import SubIssue

_SUBISSUE = SubIssueMother.pending().number
_BRANCH = "slice/05-prechecks-deterministas"


class TestConductSliceStartingANewRun:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.about_to_start())

    def test_the_understanding_of_the_chosen_slice_is_written_on_its_subissue(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.repository.write_understanding.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, understanding=Conductor.UNDERSTANDING
        )

    def test_the_harness_asked_for_the_understanding_is_given_the_subissue_the_parent_and_where_it_runs(self) -> None:
        conductor = self._conductor()
        chosen = SelectSliceResultMother.about_to_start()

        conductor.conduct()

        conductor.understanding.write.assert_called_once_with(
            subissue=chosen.subissue,
            parent=chosen.parent,
            repo=Conductor.REPO,
            worktree=Conductor.WORKTREE,
            alignment=Alignment(),
        )

    def test_a_call_that_leaves_no_usable_understanding_stops_before_anything_is_written_or_branched(self) -> None:
        conductor = self._conductor()
        conductor.understanding.write.side_effect = InvalidUnderstandingReportError("blank text")

        with pytest.raises(InvalidUnderstandingReportError):
            conductor.conduct()

        assert conductor.repository.write_understanding.call_count == 0
        assert conductor.repository.pause_for_alignment.call_count == 0
        assert conductor.branches.create.call_count == 0
        assert conductor.repository.write_run.call_count == 0

    def test_the_invocation_that_asks_for_alignment_ticks_instead_of_writing_any_code(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start(), budgets=Budgets(total_wait_seconds=0))

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert result.halt is Halt.WAIT_EXHAUSTED

    def test_the_run_pauses_on_the_in_progress_label_it_wrote_when_selected_not_the_one_the_subissue_carried(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.repository.pause_for_alignment.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS
        )

    def test_a_subissue_with_no_label_yet_is_marked_in_progress_without_asking_gh_to_remove_one_that_is_not_there(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start(subissue=SubIssueMother.unlabelled()))

        conductor.conduct()

        conductor.repository.write_label.assert_any_call(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=None, add=IssueLabel.IN_PROGRESS
        )
        conductor.repository.pause_for_alignment.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS
        )

    def test_selecting_a_slice_marks_the_subissue_in_progress_before_the_understanding_call(self) -> None:
        conductor = self._conductor()
        manager = Mock()
        manager.attach_mock(conductor.repository.write_label, "write_label")
        manager.attach_mock(conductor.understanding.write, "understand")

        conductor.conduct()

        assert [call[0] for call in manager.mock_calls][:2] == ["write_label", "understand"]
        conductor.repository.write_label.assert_any_call(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.PENDING, add=IssueLabel.IN_PROGRESS
        )

    def test_reinvoking_a_subissue_already_marked_in_progress_does_not_write_the_label_again(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.about_to_start(subissue=SubIssueMother.carrying(IssueLabel.IN_PROGRESS))
        )

        conductor.conduct()

        assert conductor.repository.write_label.call_count == 0
        assert conductor.understanding.write.call_count == 1

    def test_the_branch_of_the_slice_is_cut_from_the_declared_base(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.branches.create.assert_called_once_with(
            worktree=Conductor.WORKTREE, name=_BRANCH, base=Conductor.BASE
        )

    def test_publishing_the_understanding_persists_only_the_spend_because_the_response_is_what_decides_to_start(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.repository.write_run.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            run=Run(step=Step.UNDERSTAND, spend=HarnessSpendMother.of_the_understanding_call()),
        )

    def test_a_pause_that_never_lands_still_persists_the_spend_already_paid_but_cuts_no_branch(self) -> None:
        conductor = self._conductor()
        conductor.repository.pause_for_alignment.side_effect = OSError("gh: rate limited")

        with pytest.raises(OSError, match="rate limited"):
            conductor.conduct()

        conductor.repository.write_run.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            run=Run(step=Step.UNDERSTAND, spend=HarnessSpendMother.of_the_understanding_call()),
        )
        assert conductor.branches.create.call_count == 0

    def test_an_understanding_whose_comment_never_lands_still_persists_the_spend_already_paid(self) -> None:
        conductor = self._conductor()
        conductor.repository.write_understanding.side_effect = OSError("gh: rate limited")

        with pytest.raises(OSError, match="rate limited"):
            conductor.conduct()

        conductor.repository.write_run.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            run=Run(step=Step.UNDERSTAND, spend=HarnessSpendMother.of_the_understanding_call()),
        )
        assert conductor.repository.pause_for_alignment.call_count == 0

    def test_a_precheck_that_is_not_clear_ends_the_invocation_without_branching_or_writing_anything(self) -> None:
        conductor = self._conductor()
        conductor.prechecks.execute.return_value = PrecheckOutcome.BRANCH_ALREADY_EXISTS

        result = conductor.conduct()

        assert (result.halt, result.precheck) == (Halt.PRECHECKS_BLOCKED, PrecheckOutcome.BRANCH_ALREADY_EXISTS)
        assert conductor.branches.create.call_count == 0
        assert conductor.repository.write_understanding.call_count == 0
        assert conductor.repository.write_run.call_count == 0


class TestConductSliceRespondingToAlignment:
    @staticmethod
    def _subissue() -> SubIssue:
        return SubIssueMother.carrying(IssueLabel.AWAITING_ALIGNMENT)

    @classmethod
    def _conductor(cls, *, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.about_to_start(subissue=cls._subissue()), budgets=budgets)

    def test_no_response_yet_asks_gh_about_the_comments_of_the_one_subissue_chosen(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.NOT_YET
        )

        conductor.conduct()

        conductor.repository.read_alignment_response.assert_called_once_with(repo=Conductor.REPO, issue=_SUBISSUE)

    def test_no_response_yet_ticks_until_the_wait_is_spent_without_touching_the_harness_or_the_understanding_comment(
        self,
    ) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.NOT_YET
        )

        result = conductor.conduct()

        assert result.halt is Halt.WAIT_EXHAUSTED
        assert conductor.implement.execute.call_count == 0
        assert conductor.understanding.write.call_count == 0
        assert conductor.repository.write_understanding.call_count == 0
        assert conductor.repository.write_run.call_count == 0

    def test_a_response_that_only_appears_on_the_second_tick_still_starts_the_implementation(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=60))
        conductor.repository.read_alignment_response.side_effect = [
            AlignmentResponse(kind=AlignmentResponseKind.NOT_YET),
            AlignmentResponse(kind=AlignmentResponseKind.GO),
        ]

        conductor.conduct()

        assert conductor.repository.read_alignment_response.call_count == 2
        assert conductor.implement.execute.call_count == 1

    def test_a_review_rewrites_the_understanding_with_the_correction_it_carried(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"
        )

        conductor.conduct()

        conductor.understanding.write.assert_called_once_with(
            subissue=self._subissue(),
            parent=SelectSliceResultMother.about_to_start().parent,
            repo=Conductor.REPO,
            worktree=Conductor.WORKTREE,
            alignment=Alignment(agreed=Conductor.UNDERSTANDING, correction="la senal no esta exenta"),
        )

    def test_a_review_publishes_the_rewritten_understanding_and_keeps_waiting_until_the_wait_is_spent(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"
        )

        result = conductor.conduct()

        conductor.repository.write_understanding.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, understanding=Conductor.UNDERSTANDING
        )
        assert result.halt is Halt.WAIT_EXHAUSTED

    def test_a_review_answered_by_a_go_on_the_next_tick_publishes_once_and_starts_implementing(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=60))
        conductor.repository.read_alignment_response.side_effect = [
            AlignmentResponse(kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"),
            AlignmentResponse(kind=AlignmentResponseKind.GO),
        ]

        conductor.conduct()

        assert conductor.repository.read_alignment_response.call_count == 2
        assert conductor.understanding.write.call_count == 1
        assert conductor.implement.execute.call_count == 1

    def test_a_review_pauses_no_further_and_cuts_no_branch_but_still_persists_the_spend(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"
        )

        conductor.conduct()

        assert conductor.repository.pause_for_alignment.call_count == 0
        assert conductor.branches.create.call_count == 0
        conductor.repository.write_run.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            run=Run(step=Step.UNDERSTAND, spend=HarnessSpendMother.of_the_understanding_call()),
        )

    def test_a_go_persists_the_initial_run_and_starts_implementing_in_the_same_invocation(self) -> None:
        conductor = self._conductor()
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.GO)

        conductor.conduct()

        conductor.repository.write_run.assert_any_call(
            repo=Conductor.REPO, issue=_SUBISSUE, run=RunMother.implementing()
        )
        assert conductor.implement.execute.call_count == 1

    def test_a_go_moves_the_label_to_in_progress_before_the_implementer_is_asked_to_start(self) -> None:
        conductor = self._conductor()
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.GO)
        manager = Mock()
        manager.attach_mock(conductor.repository.write_label, "write_label")
        manager.attach_mock(conductor.implement.execute, "implement")

        conductor.conduct()

        assert [call[0] for call in manager.mock_calls][:2] == ["write_label", "implement"]
        conductor.repository.write_label.assert_any_call(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.AWAITING_ALIGNMENT, add=IssueLabel.IN_PROGRESS
        )

    def test_a_go_asks_the_harness_for_no_understanding_of_its_own(self) -> None:
        conductor = self._conductor()
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.GO)

        conductor.conduct()

        assert conductor.understanding.write.call_count == 0

    def test_a_go_carries_forward_whatever_was_spent_while_asking_for_alignment(self) -> None:
        spend = HarnessSpendMother.of_the_understanding_call()
        conductor = Conductor(
            chosen=SelectSliceResultMother.about_to_start(subissue=SubIssueMother.paused_after_spending(spend))
        )
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.GO)

        conductor.conduct()

        conductor.repository.write_run.assert_any_call(
            repo=Conductor.REPO, issue=_SUBISSUE, run=Run(step=Step.IMPLEMENT, spend=spend)
        )
        assert conductor.implement.execute.call_count == 1


class TestConductSliceRespondingToAlignmentWithAMismatchedLabel:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(
            chosen=SelectSliceResultMother.about_to_start(
                subissue=SubIssueMother.understanding_published_but_relabelled_by_hand()
            ),
            budgets=budgets,
        )

    def test_a_label_moved_by_hand_still_reads_the_pending_response_instead_of_publishing_again(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.NOT_YET
        )

        conductor.conduct()

        conductor.repository.read_alignment_response.assert_called_once_with(repo=Conductor.REPO, issue=_SUBISSUE)
        assert conductor.understanding.write.call_count == 0
        assert conductor.repository.pause_for_alignment.call_count == 0

    def test_a_go_read_despite_the_mismatched_label_still_starts_implementing(self) -> None:
        conductor = self._conductor()
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.GO)

        conductor.conduct()

        assert conductor.understanding.write.call_count == 0
        assert conductor.implement.execute.call_count == 1


class TestConductSliceClosingAMergeMissedBetweenInvocations:
    @staticmethod
    def _conductor(*, dangling: tuple[SubIssue, ...]) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.about_to_start(dangling=dangling))

    def test_a_dangling_subissue_whose_pull_request_merged_writes_its_durable_row_as_merged(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        recorded = conductor.metrics.record.call_args_list[0].args[0]
        assert (recorded.repo, recorded.slice_id, recorded.name, recorded.state, recorded.run) == (
            Conductor.REPO,
            dangling.slice_id,
            dangling.name,
            RunState.MERGED,
            dangling.run,
        )

    def test_a_dangling_subissue_whose_pull_request_merged_drops_the_label_it_still_carried(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        conductor.repository.remove_label.assert_any_call(
            repo=Conductor.REPO, issue=dangling.number, remove=dangling.label
        )

    def test_a_dangling_subissue_whose_pull_request_closed_without_merging_is_left_untouched(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.forum.pull_request_state.return_value = PullRequestState.CLOSED

        conductor.conduct()

        assert conductor.metrics.record.call_count == 0
        assert conductor.repository.remove_label.call_count == 0

    def test_a_dangling_subissue_with_no_pull_request_found_for_its_branch_is_left_untouched(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.forum.any_pull_request.return_value = None

        conductor.conduct()

        assert conductor.forum.pull_request_state.call_count == 0
        assert conductor.metrics.record.call_count == 0

    def test_the_pull_request_asked_about_is_the_one_open_on_the_dangling_subissues_own_branch(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        conductor.forum.any_pull_request.assert_any_call(repo=Conductor.REPO, branch=dangling.branch)

    def test_an_invocation_with_nothing_dangling_neither_records_nor_removes_a_label_for_it(self) -> None:
        conductor = self._conductor(dangling=())

        conductor.conduct()

        assert conductor.metrics.record.call_count == 0
        assert conductor.repository.remove_label.call_count == 0

    def test_a_dangling_subissue_whose_pull_request_merged_also_asks_to_close_the_parent_of_this_issue(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        conductor.close.execute.assert_any_call(CloseParentParams(repo=Conductor.REPO, issue=Conductor.ISSUE))

    def test_a_dangling_subissue_whose_pull_request_closed_without_merging_asks_to_close_nothing(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.forum.pull_request_state.return_value = PullRequestState.CLOSED

        conductor.conduct()

        assert conductor.close.execute.call_count == 0


class TestConductSliceWhenTheNamedSliceCannotBeSelected:
    @staticmethod
    def _unselectable(*, dangling: tuple[SubIssue, ...]) -> NoSliceLeftError:
        error = NoSliceLeftError("slice-12 of issue 38 cannot be run: it is closed, blocked or aborted")
        error.dangling = dangling

        return error

    def test_a_run_left_dangling_still_closes_and_writes_its_row_instead_of_the_selection_failing_silently(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        dangling = SubIssueMother.dangling()
        conductor.select.execute.side_effect = self._unselectable(dangling=(dangling,))

        with pytest.raises(NoSliceLeftError):
            conductor.conduct()

        recorded = conductor.metrics.record.call_args_list[0].args[0]
        assert (recorded.slice_id, recorded.state) == (dangling.slice_id, RunState.MERGED)

    def test_the_slice_that_cannot_be_selected_still_fails_the_invocation_once_the_dangling_run_is_closed(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=(SubIssueMother.dangling(),))

        with pytest.raises(NoSliceLeftError, match="slice-12"):
            conductor.conduct()

    def test_nothing_left_dangling_records_no_row_before_the_selection_failure_propagates(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=())

        with pytest.raises(NoSliceLeftError):
            conductor.conduct()

        assert conductor.metrics.record.call_count == 0


class TestConductSliceResumingAnInterruptedRun:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging()))

    def test_a_run_persisted_at_verify_judges_instead_of_implementing_and_running_the_controls_again(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert (conductor.implement.execute.call_count, conductor.controls.run.call_count) == (0, 0)
        assert conductor.verify.execute.call_count == 1

    def test_a_run_that_was_already_aligned_does_not_go_through_the_prechecks_again(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.prechecks.execute.call_count == 0
        assert conductor.repository.pause_for_alignment.call_count == 0

    def test_a_persisted_run_whose_subissue_declares_another_repo_is_stopped_at_this_gate_too(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.judging(), subissue=SubIssueMother.of_another_repo())
        )

        result = conductor.conduct()

        assert (result.halt, result.precheck) == (Halt.PRECHECKS_BLOCKED, PrecheckOutcome.SLICE_IN_ANOTHER_REPO)
        assert conductor.verify.execute.call_count == 0
        assert conductor.repository.write_run.call_count == 0


class TestConductSliceResumingWithSpendAlreadyPersisted:
    def test_reinvoking_does_not_reset_the_budget_because_the_prior_spend_travels_with_the_run(self) -> None:
        prior = HarnessSpendMother.of_the_implementer_call()
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.judging_after_spending(prior)),
            budgets=Budgets(slice_cost_usd=prior.cost_usd),
        )

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 0
        assert result.state is RunState.ABORTED_BUDGET

    def test_the_durable_row_of_a_reinvoked_run_still_carries_the_cost_paid_in_an_earlier_invocation(self) -> None:
        prior = HarnessSpendMother.of_the_implementer_call()
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging_after_spending(prior)))

        conductor.conduct()

        recorded: ClosedSlice = conductor.metrics.record.call_args.args[0]
        assert recorded.spends == (prior, HarnessSpendMother.of_the_judge_call())

    def test_the_run_written_after_a_paid_call_persists_the_cumulative_spend_and_not_only_this_calls(self) -> None:
        prior = HarnessSpendMother.of_the_implementer_call()
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging_after_spending(prior)))

        conductor.conduct()

        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert written[0].spend == HarnessSpend.summing((prior, HarnessSpendMother.of_the_judge_call()))


class TestConductSliceOnTheHappyPath:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_it_walks_the_steps_in_the_order_the_state_machine_dictates_and_persists_each_one(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestState.OPEN

        result = conductor.conduct()

        assert [call.kwargs["run"].step for call in conductor.repository.write_run.call_args_list] == [
            Step.RUN_CONTROLS,
            Step.VERIFY,
            Step.OPEN_PULL_REQUEST,
            Step.AWAIT_CI,
            Step.AWAIT_MERGE,
        ]
        assert (result.state, result.step) == (RunState.OPEN, Step.AWAIT_MERGE)

    def test_the_index_is_staged_with_exactly_what_the_implementer_reported(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.stage.execute.call_args.args[0].paths == ImplementationMother.of_two_paths().paths

    def test_the_pull_request_is_opened_on_the_branch_of_the_slice_with_what_the_writer_composed(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        delivered = conductor.deliver.execute.call_args.args[0]
        assert (delivered.worktree, delivered.repo, delivered.branch, delivered.base) == (
            Conductor.WORKTREE,
            Conductor.REPO,
            _BRANCH,
            Conductor.BASE,
        )
        assert (delivered.title, delivered.body) == (Conductor.TITLE, Conductor.BODY)

    def test_the_pull_request_body_is_asked_for_with_what_the_implementer_declared_left_out(self) -> None:
        conductor = self._conductor()
        conductor.implement.execute.return_value = ImplementationMother.with_debt()

        conductor.conduct()

        assert conductor.pull_request.body.call_args.kwargs["debt"] == ImplementationMother.with_debt().left_out

    def test_the_pull_request_it_just_opened_is_the_one_it_asks_the_ci_and_the_merge_about(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.ci.status.call_args.kwargs == {"repo": Conductor.REPO, "pull_request": Conductor.PULL_REQUEST}
        assert conductor.forum.pull_request_state.call_args.kwargs == {
            "repo": Conductor.REPO,
            "number": Conductor.PULL_REQUEST,
        }
        assert conductor.forum.open_pull_request.call_count == 0

    def test_a_green_ci_moves_the_label_to_awaiting_merge_because_the_merge_is_a_human_decision(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestState.OPEN

        conductor.conduct()

        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.AWAITING_MERGE
        )

    def test_a_merged_pull_request_closes_the_run_and_the_invocation_reports_its_number(self) -> None:
        conductor = self._conductor()

        result = conductor.conduct()

        assert (result.halt, result.state, result.pull_request) == (
            Halt.RUN_CLOSED,
            RunState.MERGED,
            Conductor.PULL_REQUEST,
        )

    def test_a_merged_run_writes_no_label_because_github_closes_the_subissue_on_the_merge(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

        conductor.conduct()

        assert conductor.repository.write_label.call_count == 0

    def test_a_merged_run_still_removes_whatever_label_the_subissue_carried_so_the_two_do_not_contradict(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

        conductor.conduct()

        conductor.repository.remove_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS
        )

    def test_a_merged_run_that_carried_no_label_removes_none_because_there_is_nothing_to_retire(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge(), label=None))

        conductor.conduct()

        assert conductor.repository.remove_label.call_count == 0

    def test_the_durable_row_carries_the_slice_the_state_and_every_call_that_was_paid_for(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        recorded = self._recorded(conductor.metrics)
        assert (recorded.repo, recorded.slice_id, recorded.name) == (
            Conductor.REPO,
            "slice-05",
            "prechecks-deterministas",
        )
        assert recorded.state is RunState.MERGED
        assert recorded.spends == (
            HarnessSpendMother.of_the_implementer_call(),
            HarnessSpendMother.of_the_judge_call(),
        )

    @staticmethod
    def _recorded(metrics: Mock) -> ClosedSlice:
        closed: ClosedSlice = metrics.record.call_args.args[0]

        return closed


class TestConductSliceReportingEvents:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_every_transition_reports_the_slice_the_step_it_lands_on_the_instant_and_the_spend_paid_so_far(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        after_the_implementer = HarnessSpendMother.of_the_implementer_call()
        after_the_judge = HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )
        emitted = conductor.emitted_events
        assert [(e.slice_id, e.step, e.at, e.spend) for e in emitted] == [
            ("slice-05", Step.RUN_CONTROLS, Conductor.NOW, after_the_implementer),
            ("slice-05", Step.VERIFY, Conductor.NOW, after_the_implementer),
            ("slice-05", Step.OPEN_PULL_REQUEST, Conductor.NOW, after_the_judge),
            ("slice-05", Step.AWAIT_CI, Conductor.NOW, after_the_judge),
            ("slice-05", Step.AWAIT_MERGE, Conductor.NOW, after_the_judge),
            ("slice-05", Step.AWAIT_MERGE, Conductor.NOW, after_the_judge),
        ]

    def test_the_happy_path_reports_advancing_for_every_step_until_the_run_closes_and_then_reports_closed(
        self,
    ) -> None:
        conductor = self._conductor()

        conductor.conduct()

        emitted = conductor.emitted_events
        assert [e.status for e in emitted] == [EventStatus.ADVANCING] * 5 + [EventStatus.CLOSED]

    def test_a_pending_merge_reports_awaiting_a_person_because_the_merge_is_a_human_decision(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestState.OPEN

        conductor.conduct()

        emitted = conductor.emitted_events
        assert (emitted[-1].step, emitted[-1].status) == (Step.AWAIT_MERGE, EventStatus.AWAITING_PERSON)

    def test_a_pending_ci_reports_waiting_because_no_person_is_deciding_anything_yet(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()),
            budgets=Budgets(total_wait_seconds=90),
        )
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        emitted = conductor.emitted_events
        assert [e.status for e in emitted] == [EventStatus.WAITING] * 3


class TestConductSliceChainingDeployWatchAfterAMerge:
    @staticmethod
    def _conductor(*, subissue: SubIssue) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge(), subissue=subissue))

    def test_a_merge_with_a_signal_declared_chains_deploy_watch_with_that_signal_and_the_repo_of_the_issue(
        self,
    ) -> None:
        subissue = SubIssueMother.declaring_a_signal()
        conductor = self._conductor(subissue=subissue)

        conductor.conduct()

        conductor.deploy_watch.watch.assert_called_once_with(
            worktree=Conductor.WORKTREE, repo=Conductor.REPO, signal=subissue.signal
        )

    def test_a_merge_whose_signal_is_exempt_chains_nothing(self) -> None:
        conductor = self._conductor(subissue=SubIssueMother.pending())

        conductor.conduct()

        assert conductor.deploy_watch.watch.call_count == 0

    def test_a_close_that_does_not_merge_the_slice_chains_nothing_even_with_a_signal_declared(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.judging(), subissue=SubIssueMother.declaring_a_signal()
            ),
            budgets=Budgets(verify_retries=0),
        )
        conductor.verify.execute.return_value = VerificationMother.vetoing(VerdictMother.failing())

        conductor.conduct()

        assert conductor.deploy_watch.watch.call_count == 0


class TestConductSliceClosingTheParentAfterAMerge:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

    def test_a_merged_run_asks_to_close_the_parent_of_the_issue_this_slice_belongs_to(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.close.execute.assert_called_once_with(CloseParentParams(repo=Conductor.REPO, issue=Conductor.ISSUE))

    def test_a_close_that_does_not_merge_the_slice_asks_to_close_nothing(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets(hygiene_retries=0)
        )
        conductor.stage.execute.side_effect = DirtyIndexError("src/leftover.py (not-declared)")

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_HYGIENE
        assert conductor.close.execute.call_count == 0


class TestConductSliceWhenTheControlsComeBackRed:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_every_declared_control_runs_even_after_one_of_them_has_already_failed(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.implementing(), parent=ParentIssueMother.with_two_controls()
            ),
            budgets=Budgets(control_retries=0),
        )
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        conductor.conduct()

        assert [call.args[0].name for call in conductor.controls.run.call_args_list] == ["lint", "tests"]

    def test_the_log_of_the_red_control_reaches_the_next_implementation_as_a_path(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=1))
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        conductor.conduct()

        retried = conductor.implement.execute.call_args_list[-1].args[0]
        assert retried.control_logs == (ControlOutcomeMother.LOG,)

    def test_the_controls_are_run_in_the_worktree_and_leave_their_log_under_a_round_specific_directory(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.controls.run.call_args.kwargs == {
            "repo": Conductor.WORKTREE,
            "out": Conductor.LOGS / "round-1",
        }

    def test_each_retried_round_of_controls_writes_under_a_directory_of_its_own(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=1))
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        conductor.conduct()

        outs = [call.kwargs["out"] for call in conductor.controls.run.call_args_list]
        assert outs == [Conductor.LOGS / "round-1", Conductor.LOGS / "round-2"]

    def test_the_exhausted_control_budget_closes_the_run_writes_its_label_and_records_the_row(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=0))
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_CONTROLS
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CONTROLS
        )
        assert conductor.metrics.record.call_args.args[0].state is RunState.BLOCKED_CONTROLS

    def test_a_repo_exempt_from_controls_runs_none_of_them_and_goes_straight_to_the_judge(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.running_the_controls(), parent=ParentIssueMother.with_exempt_controls()
            )
        )

        conductor.conduct()

        assert conductor.controls.run.call_count == 0
        assert conductor.verify.execute.call_count == 1


class TestConductSliceWhenTheStagedIndexIsRejected:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_a_dirty_index_fails_the_step_without_running_a_single_control(self) -> None:
        conductor = self._conductor(budgets=Budgets(hygiene_retries=0))
        conductor.stage.execute.side_effect = DirtyIndexError("the staged index is not what the implementer reported")

        result = conductor.conduct()

        assert conductor.controls.run.call_count == 0
        assert result.state is RunState.BLOCKED_HYGIENE

    def test_a_rejection_spends_no_retry_of_the_controls_even_when_their_own_budget_is_exhausted(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=0))
        conductor.stage.execute.side_effect = [DirtyIndexError("src/leftover.py (not-declared)"), None]

        result = conductor.conduct()

        assert result.state is RunState.MERGED

    def test_the_reason_the_index_was_refused_reaches_the_next_implementer_so_it_does_not_repeat_it(self) -> None:
        conductor = self._conductor()
        conductor.stage.execute.side_effect = [DirtyIndexError("src/leftover.py (not-declared)"), None]

        conductor.conduct()

        ordered = [call.args[0].hygiene_refusal for call in conductor.implement.execute.call_args_list]
        assert ordered[0] == ""
        assert "src/leftover.py (not-declared)" in ordered[1]

    def test_the_refusal_does_not_travel_to_a_round_whose_controls_did_run(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=2))
        conductor.stage.execute.side_effect = [DirtyIndexError("src/leftover.py (not-declared)"), None, None]
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        conductor.conduct()

        ordered = [call.args[0].hygiene_refusal for call in conductor.implement.execute.call_args_list]
        assert ordered[2] == ""

    def test_the_exhausted_hygiene_budget_closes_the_run_writes_its_label_and_records_the_row(self) -> None:
        conductor = self._conductor(budgets=Budgets(hygiene_retries=0))
        conductor.stage.execute.side_effect = DirtyIndexError("src/leftover.py (not-declared)")

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_HYGIENE
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_HYGIENE
        )
        assert conductor.metrics.record.call_args.args[0].state is RunState.BLOCKED_HYGIENE


class TestConductSliceWhenAControlCannotBeMeasured:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_a_control_that_could_not_run_is_retried_on_the_same_step_instead_of_being_read_as_red(self) -> None:
        conductor = self._conductor()
        conductor.controls.run.side_effect = [ControlOutcomeMother.unknown(), ControlOutcomeMother.green()]

        result = conductor.conduct()

        assert conductor.controls.run.call_count == 2
        assert conductor.implement.execute.call_count == 1
        assert IssueLabel.BLOCKED_CONTROLS not in [
            call.kwargs["add"] for call in conductor.repository.write_label.call_args_list
        ]
        assert result.state is RunState.MERGED

    def test_a_control_that_never_settles_waits_out_the_invocation_instead_of_blocking_the_slice(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=0))
        conductor.controls.run.return_value = ControlOutcomeMother.unknown()

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert result.halt is Halt.WAIT_EXHAUSTED

    def test_a_red_control_still_blocks_even_when_another_one_could_not_run(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.implementing(), parent=ParentIssueMother.with_two_controls()
            ),
            budgets=Budgets(control_retries=0),
        )
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.unknown()]

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_CONTROLS


class TestConductSliceWhenTheJudgeSpeaks:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging()), budgets=budgets)

    def test_a_veto_sends_the_findings_it_raised_to_the_implementation_that_has_to_fix_them(self) -> None:
        raised = FindingMother.without_line()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.return_value = VerificationMother.vetoing(VerdictMother.failing(raised))

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].findings == (raised,)

    def test_a_pass_that_still_raised_findings_corrects_them_before_delivering(self) -> None:
        raised = FindingMother.with_line()
        conductor = self._conductor(budgets=Budgets(correction_retries=1))
        conductor.verify.execute.return_value = VerificationMother.ordering_corrections(raised)

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].findings == (raised,)
        assert conductor.deliver.execute.call_count == 1

    def test_a_pass_whose_findings_are_all_low_severity_delivers_without_asking_the_implementer_again(self) -> None:
        accepted = FindingMother.low_severity()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.return_value = VerificationMother.approving_with_accepted_debt(accepted)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert conductor.deliver.execute.call_count == 1

    def test_a_pass_whose_findings_are_all_low_severity_puts_them_in_front_of_whoever_reviews_the_pull_request(
        self,
    ) -> None:
        accepted = FindingMother.low_severity()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.return_value = VerificationMother.approving_with_accepted_debt(accepted)

        conductor.conduct()

        assert conductor.pull_request.body.call_args.kwargs["findings"] == (accepted,)

    def test_the_durable_row_keeps_the_findings_of_every_round_because_one_caught_and_fixed_still_happened(
        self,
    ) -> None:
        raised = FindingMother.without_line()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(raised)),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        assert conductor.metrics.record.call_args.args[0].findings == (raised,)

    def test_the_durable_row_keeps_the_findings_of_the_last_round_apart_so_a_pass_with_one_is_never_ambiguous(
        self,
    ) -> None:
        raised = FindingMother.without_line()
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(raised)),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        recorded: ClosedSlice = conductor.metrics.record.call_args.args[0]
        assert recorded.findings == (raised,)
        assert recorded.findings_of_the_last_round == ()

    def test_a_second_round_is_sent_only_what_the_last_verdict_raised_because_the_earlier_ones_may_be_fixed(
        self,
    ) -> None:
        first = FindingMother.without_line()
        second = FindingMother.without_line(path="src/y.py")
        conductor = self._conductor(budgets=Budgets(verify_retries=2))
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing(first)),
            VerificationMother.vetoing(VerdictMother.failing(second)),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].findings == (second,)
        assert conductor.metrics.record.call_args.args[0].findings == (first, second)

    def test_a_veto_with_no_budget_left_closes_the_run_as_blocked_by_the_judge(self) -> None:
        conductor = self._conductor(budgets=Budgets(verify_retries=0))
        conductor.verify.execute.return_value = VerificationMother.vetoing(VerdictMother.failing())

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_VERIFY
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_VERIFY
        )
        assert conductor.metrics.record.call_args.args[0].findings == VerdictMother.failing().findings

    def test_a_discarded_verdict_spends_no_verify_retry_and_still_counts_what_the_call_cost(self) -> None:
        conductor = self._conductor()
        conductor.verify.execute.side_effect = [RejectionMother.incoherent_verdict(), VerificationMother.passing()]

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert (recorded.run.verify_discards, recorded.run.verify_retries) == (1, 0)
        assert recorded.spend.calls == 2
        assert recorded.discard_cause is DiscardCause.INCOHERENT_VERDICT

    def test_a_call_that_left_no_verdict_at_all_is_discarded_as_a_failed_call_and_not_as_an_incoherent_one(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.verify.execute.side_effect = [RejectionMother.denied_read(), VerificationMother.passing()]

        conductor.conduct()

        assert conductor.metrics.record.call_args.args[0].discard_cause is DiscardCause.FAILED_CALL


class TestConductSliceWhenTheCostOfTheSliceRunsOut:
    def test_discard_after_discard_closes_the_run_writes_its_label_and_records_the_row(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.1))
        conductor.verify.execute.side_effect = [
            RejectionMother.incoherent_verdict(),
            RejectionMother.incoherent_verdict(),
        ]

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 2
        assert result.state is RunState.ABORTED_BUDGET
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.ABORTED_BUDGET
        )
        assert conductor.metrics.record.call_args.args[0].state is RunState.ABORTED_BUDGET

    def test_a_discard_with_cost_left_asks_the_judge_again_instead_of_closing(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.2))
        conductor.verify.execute.side_effect = [RejectionMother.incoherent_verdict(), VerificationMother.passing()]

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 2
        assert result.state is RunState.MERGED

    def test_a_call_the_harness_never_measured_closes_the_run_instead_of_spinning_for_a_cost_nobody_can_add_up(
        self,
    ) -> None:
        conductor = self._judging(budgets=Budgets())
        conductor.verify.execute.side_effect = [
            RejectionMother.envelope_nobody_could_parse(),
            VerificationMother.passing(),
        ]

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 1
        assert result.state is RunState.ABORTED_BUDGET

    def test_a_call_with_no_measurement_closes_the_run_even_after_an_earlier_call_of_the_run_was_measured(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets())
        conductor.verify.execute.side_effect = [
            RejectionMother.envelope_nobody_could_parse(),
            RejectionMother.envelope_nobody_could_parse(),
        ]

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert conductor.verify.execute.call_count == 1
        assert result.state is RunState.ABORTED_BUDGET

    def test_an_implementation_that_spent_the_whole_cost_closes_before_running_a_single_control(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()),
            budgets=Budgets(slice_cost_usd=0.1),
        )

        result = conductor.conduct()

        assert (conductor.stage.execute.call_count, conductor.controls.run.call_count) == (0, 0)
        assert result.state is RunState.ABORTED_BUDGET

    def test_a_step_that_never_called_the_harness_is_not_measured_against_the_cost_of_the_slice(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()), budgets=Budgets(slice_cost_usd=0.1)
        )

        result = conductor.conduct()

        assert result.state is RunState.MERGED

    def test_a_pass_that_alone_exceeds_the_cost_still_merges_because_it_was_already_paid_for(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.01))
        conductor.verify.execute.return_value = VerificationMother.passing()

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 1
        assert result.state is RunState.MERGED

    def test_a_pass_with_corrections_still_delivers_over_budget_because_delivering_costs_no_harness(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.01, correction_retries=0))
        conductor.verify.execute.return_value = VerificationMother.ordering_corrections(FindingMother.with_line())

        result = conductor.conduct()

        assert conductor.verify.execute.call_count == 1
        assert result.state is RunState.MERGED

    def test_the_cost_of_an_over_budget_pass_still_blocks_the_next_call_the_harness_would_make(self) -> None:
        conductor = self._judging(budgets=Budgets(slice_cost_usd=0.01, ci_retries=1))
        conductor.verify.execute.return_value = VerificationMother.passing()
        conductor.ci.status.return_value = CiStatus.RED

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert result.state is RunState.ABORTED_BUDGET

    @staticmethod
    def _judging(*, budgets: Budgets) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging()), budgets=budgets)


class TestConductSliceWhenThePullRequestWasClosedWithoutMerging:
    @staticmethod
    def _conductor() -> Conductor:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))
        conductor.forum.pull_request_state.return_value = PullRequestState.CLOSED

        return conductor

    def test_the_invocation_ends_instead_of_ticking_for_a_merge_that_can_no_longer_arrive(self) -> None:
        conductor = self._conductor()

        result = conductor.conduct()

        assert result.halt is Halt.PULL_REQUEST_CLOSED
        assert conductor.clock.sleep.call_count == 0
        assert conductor.forum.pull_request_state.call_count == 1

    def test_the_run_is_left_open_on_its_step_and_no_durable_row_is_written_because_it_did_not_close(self) -> None:
        conductor = self._conductor()

        result = conductor.conduct()

        assert (result.halt, result.state, result.step, result.pull_request) == (
            Halt.PULL_REQUEST_CLOSED,
            RunState.OPEN,
            Step.AWAIT_MERGE,
            Conductor.PULL_REQUEST,
        )
        assert conductor.metrics.record.call_count == 0


class TestConductSliceWaitingForTheMerge:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()), budgets=budgets)

    def test_a_merge_that_never_arrives_flags_the_subissue_that_its_pull_request_is_still_draft(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestState.OPEN

        result = conductor.conduct()

        assert result.halt is Halt.WAIT_EXHAUSTED
        conductor.repository.flag_draft_pull_request.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, pull_request=Conductor.PULL_REQUEST
        )

    def test_a_ci_wait_that_is_exhausted_flags_nothing_because_the_pull_request_is_not_awaiting_a_merge_yet(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()),
            budgets=Budgets(total_wait_seconds=30),
        )
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        assert conductor.repository.flag_draft_pull_request.call_count == 0


class TestConductSliceWaitingForTheCi:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()), budgets=budgets)

    def test_a_pending_ci_ticks_with_the_separation_the_budget_declares_until_the_total_wait_is_spent(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=90))
        conductor.ci.status.return_value = CiStatus.PENDING

        result = conductor.conduct()

        assert [call.kwargs["seconds"] for call in conductor.clock.sleep.call_args_list] == [30, 30, 30]
        assert (result.halt, result.state, result.step) == (Halt.WAIT_EXHAUSTED, RunState.OPEN, Step.AWAIT_CI)

    def test_a_tick_that_changes_nothing_does_not_rewrite_the_state_of_the_run(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=30))
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        assert conductor.repository.write_run.call_count == 0

    def test_an_invocation_that_ends_without_closing_the_run_writes_no_durable_row(self) -> None:
        conductor = self._conductor(budgets=Budgets(total_wait_seconds=30))
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        assert conductor.metrics.record.call_count == 0

    def test_a_resumed_run_finds_the_pull_request_of_its_branch_whatever_state_it_is_already_in(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.forum.any_pull_request.assert_called_with(repo=Conductor.REPO, branch=_BRANCH)
        assert conductor.forum.open_pull_request.call_count == 0
        assert conductor.ci.status.call_args.kwargs["pull_request"] == Conductor.PULL_REQUEST

    def test_a_resumed_run_whose_branch_never_had_a_pull_request_raises_instead_of_asking_about_nothing(self) -> None:
        conductor = self._conductor()
        conductor.forum.any_pull_request.return_value = None

        with pytest.raises(NoPullRequestError, match=_BRANCH):
            conductor.conduct()

    def test_a_ci_with_no_checks_closes_the_run_only_after_the_whole_grace_window(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == 2
        assert result.state is RunState.BLOCKED_CI_INDETERMINATE
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            remove=IssueLabel.IN_PROGRESS,
            add=IssueLabel.BLOCKED_CI_INDETERMINATE,
        )

    def test_a_ci_state_nobody_can_read_counts_as_indeterminate_and_not_as_a_failure_of_the_slice(self) -> None:
        conductor = self._conductor(budgets=Budgets(indeterminate_ticks=1))
        conductor.ci.status.return_value = CiStatus.UNKNOWN

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert result.state is RunState.BLOCKED_CI_INDETERMINATE

    def test_a_red_ci_sends_the_slice_back_to_be_implemented_and_closes_when_that_budget_runs_out(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.RED

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert result.state is RunState.BLOCKED_CI_RED
        assert conductor.metrics.record.call_args.args[0].state is RunState.BLOCKED_CI_RED
