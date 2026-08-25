from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from slice_runner.application.actions.close_parent import CloseParentParams
from slice_runner.application.actions.reopen_slice import ReopenSliceParams, ReopenSliceResult
from slice_runner.domain.alignment_response import AlignmentResponse
from slice_runner.domain.alignment_response_kind import AlignmentResponseKind
from slice_runner.domain.branch_catch_up import BranchCatchUp
from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.conflict_block_cause import ConflictBlockCause
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.event_status import EventStatus
from slice_runner.domain.exceptions import (
    CiCommandFailedError,
    DirtyIndexError,
    InvalidResolutionReportError,
    MissingBranchError,
    NoPullRequestError,
    NoSliceLeftError,
    UnreadableCiError,
)
from slice_runner.domain.halt import Halt
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.malformed_reason import MalformedReason
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.precheck_result import PrecheckResult
from slice_runner.domain.requested_change import RequestedChange
from slice_runner.domain.retry_response import RetryResponse
from slice_runner.domain.retry_response_kind import RetryResponseKind
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.run import Run
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.tests.conductor import Conductor
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.harness_call_mother import HarnessCallMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.pull_request_review_comment_mother import PullRequestReviewCommentMother
from slice_runner.tests.mothers.pull_request_review_mother import PullRequestReviewMother
from slice_runner.tests.mothers.pull_request_status_mother import PullRequestStatusMother
from slice_runner.tests.mothers.rejection_mother import RejectionMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.select_slice_result_mother import SelectSliceResultMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.understanding_mother import UnderstandingMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, VerdictMother
from slice_runner.tests.mothers.verification_mother import SliceDiffMother, VerificationMother

_RETRY_INSTRUCTION = "el control ya esta arreglado a mano"

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.domain.pull_request_review import PullRequestReview
    from slice_runner.domain.sub_issue import SubIssue

_SUBISSUE = SubIssueMother.pending().number
_BRANCH = "slice/05-prechecks-deterministas"


class TestConductSliceStartingANewRun:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.about_to_start())

    def test_a_call_that_leaves_no_usable_understanding_is_discarded_and_retried_within_budget(self) -> None:
        conductor = self._conductor()
        conductor.understanding.write.side_effect = [
            RejectionMother.invalid_understanding_report(),
            UnderstandingMother.of_the_chosen_slice(),
        ]
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.GO)
        conductor.trace.calls_of.return_value = (
            HarnessCallMother.of_the_discarded_understanding(),
            HarnessCallMother.of_the_implementer(),
            HarnessCallMother.of_the_judge(),
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_DISCARDED_UNDERSTANDING,
            spend=HarnessSpendMother.of_a_call_that_cost_nothing(),
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=HarnessSpendMother.of_the_implementer_call()
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )

        conductor.conduct()

        assert conductor.understanding.write.call_count == 2
        assert (conductor.repository.pause_for_alignment.call_count, conductor.branches.create.call_count) == (1, 1)
        recorded = conductor.closed
        assert recorded.run.understand_discards == 1
        assert recorded.discarded_call is not None
        assert recorded.discarded_call.step is Step.UNDERSTAND
        assert recorded.discarded_call.cause is DiscardCause.FAILED_CALL
        assert recorded.discarded_call.reason == "the harness returned only blank text as its understanding"
        assert recorded.spend == HarnessSpend.summing(
            (
                HarnessSpendMother.of_a_call_that_cost_nothing(),
                HarnessSpendMother.of_the_implementer_call(),
                HarnessSpendMother.of_the_judge_call(),
            )
        )

    def test_a_discard_whose_message_is_longer_than_the_reason_limit_is_recorded_with_it_truncated(self) -> None:
        conductor = self._conductor()
        conductor.understanding.write.side_effect = [
            RejectionMother.invalid_understanding_report_with_an_overlong_message(),
            UnderstandingMother.of_the_chosen_slice(),
        ]
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.GO)

        conductor.conduct()

        assert conductor.closed.discarded_call is not None
        assert conductor.closed.discarded_call.reason == "a" * 200

    def test_discard_after_discard_of_the_understanding_closes_the_run_and_writes_its_label(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start(), budgets=Budgets(slice_cost_usd=0.03))
        conductor.understanding.write.side_effect = [
            RejectionMother.invalid_understanding_report(),
            RejectionMother.invalid_understanding_report(),
        ]

        result = conductor.conduct()

        assert conductor.understanding.write.call_count == 2
        assert result.state is RunState.ABORTED_BUDGET
        conductor.repository.write_label.assert_any_call(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.AWAITING_ALIGNMENT, add=IssueLabel.ABORTED_BUDGET
        )
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.state is RunState.ABORTED_BUDGET
        assert recorded.discarded_call is not None
        assert recorded.discarded_call.step is Step.UNDERSTAND
        assert recorded.discarded_call.cause is DiscardCause.FAILED_CALL
        assert conductor.repository.pause_for_alignment.call_count == 0

    def test_the_invocation_that_asks_for_alignment_ticks_instead_of_writing_any_code(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start(), budgets=Budgets(person_wait_seconds=0))

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

    def test_the_precheck_is_asked_about_the_declared_base_before_the_branch_is_cut(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        asked = conductor.prechecks.execute.call_args.args[0]
        assert asked.base == Conductor.BASE

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
        conductor.prechecks.execute.return_value = PrecheckResult(outcome=PrecheckOutcome.BRANCH_ALREADY_EXISTS)

        result = conductor.conduct()

        assert (result.halt, result.precheck) == (
            Halt.PRECHECKS_BLOCKED,
            PrecheckResult(outcome=PrecheckOutcome.BRANCH_ALREADY_EXISTS),
        )
        assert conductor.branches.create.call_count == 0
        assert conductor.repository.write_understanding.call_count == 0
        assert conductor.repository.write_run.call_count == 0

    def test_a_precheck_with_no_reason_writes_nothing_to_the_subissue_beyond_the_halt_itself(self) -> None:
        conductor = self._conductor()
        conductor.prechecks.execute.return_value = PrecheckResult(outcome=PrecheckOutcome.BRANCH_ALREADY_EXISTS)

        conductor.conduct()

        assert conductor.repository.write_precheck_reason.call_count == 0

    def test_a_precheck_stopped_by_an_unreadable_source_writes_the_outcome_and_the_reason_on_the_subissue(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.prechecks.execute.return_value = PrecheckResult(
            outcome=PrecheckOutcome.UNREADABLE_SOURCE, reason="CLAUDE.md does not exist under the worktree"
        )

        conductor.conduct()

        conductor.repository.write_precheck_reason.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            outcome=PrecheckOutcome.UNREADABLE_SOURCE,
            reason="CLAUDE.md does not exist under the worktree",
        )


class TestConductSliceRespondingToAlignment:
    @staticmethod
    def _subissue() -> SubIssue:
        return SubIssueMother.carrying(IssueLabel.AWAITING_ALIGNMENT)

    @classmethod
    def _conductor(cls, *, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.about_to_start(subissue=cls._subissue()), budgets=budgets)

    def test_no_response_yet_ticks_until_the_wait_is_spent_without_touching_the_harness_or_the_understanding_comment(
        self,
    ) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=0))
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
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=60))
        conductor.repository.read_alignment_response.side_effect = [
            AlignmentResponse(kind=AlignmentResponseKind.NOT_YET),
            AlignmentResponse(kind=AlignmentResponseKind.GO),
        ]

        conductor.conduct()

        assert conductor.repository.read_alignment_response.call_count == 2
        assert conductor.implement.execute.call_count == 1

    def test_a_review_publishes_the_rewritten_understanding_and_keeps_waiting_until_the_wait_is_spent(self) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"
        )

        result = conductor.conduct()

        conductor.repository.write_understanding.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, understanding=Conductor.UNDERSTANDING
        )
        assert result.halt is Halt.WAIT_EXHAUSTED

    def test_a_review_answered_by_a_go_on_the_next_tick_publishes_once_and_starts_implementing(self) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=60))
        conductor.repository.read_alignment_response.side_effect = [
            AlignmentResponse(kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"),
            AlignmentResponse(kind=AlignmentResponseKind.GO),
        ]

        conductor.conduct()

        assert conductor.repository.read_alignment_response.call_count == 2
        assert conductor.understanding.write.call_count == 1
        assert conductor.implement.execute.call_count == 1

    def test_a_review_still_unanswered_on_every_tick_publishes_only_once_for_that_correction(self) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=90))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"
        )

        result = conductor.conduct()

        assert conductor.repository.read_alignment_response.call_count == 3
        assert conductor.understanding.write.call_count == 1
        assert result.halt is Halt.WAIT_EXHAUSTED

    def test_a_second_review_with_a_different_correction_still_publishes_its_own_call(self) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=60))
        conductor.repository.read_alignment_response.side_effect = [
            AlignmentResponse(kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"),
            AlignmentResponse(kind=AlignmentResponseKind.REVIEW, correction="ademas falta un criterio"),
        ]

        conductor.conduct()

        assert conductor.understanding.write.call_count == 2

    def test_a_review_pauses_no_further_and_cuts_no_branch_but_still_persists_the_spend(self) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"
        )

        conductor.conduct()

        assert conductor.repository.pause_for_alignment.call_count == 0
        assert conductor.branches.create.call_count == 0
        conductor.repository.write_run.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            run=Run(
                step=Step.UNDERSTAND,
                corrected="la senal no esta exenta",
                spend=HarnessSpendMother.of_the_understanding_call(),
            ),
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

    def test_a_tick_that_finds_the_prior_malformed_comment_already_acknowledged_answers_it_no_further(self) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=60))
        malformed = AlignmentResponse(kind=AlignmentResponseKind.MALFORMED, reason=MalformedReason.GO_CARRIES_TEXT)
        conductor.repository.read_alignment_response.side_effect = [
            malformed,
            AlignmentResponse(kind=AlignmentResponseKind.NOT_YET),
        ]

        conductor.conduct()

        assert conductor.repository.read_alignment_response.call_count == 2
        conductor.repository.write_malformed_response.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, reason=MalformedReason.GO_CARRIES_TEXT
        )
        assert conductor.implement.execute.call_count == 0

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


class TestConductSliceReinvokedWhileAwaitingAlignment:
    @staticmethod
    def _conductor(correction: str, *, budgets: Budgets | None = None) -> Conductor:
        return Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.awaiting_alignment_after_a_published_correction(correction),
                label=IssueLabel.AWAITING_ALIGNMENT,
            ),
            budgets=budgets,
        )

    def test_a_reinvocation_that_still_reads_the_correction_a_prior_invocation_already_published_writes_no_new_call(
        self,
    ) -> None:
        conductor = self._conductor("la senal no esta exenta", budgets=Budgets(person_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.REVIEW, correction="la senal no esta exenta"
        )

        result = conductor.conduct()

        assert conductor.understanding.write.call_count == 0
        assert result.halt is Halt.WAIT_EXHAUSTED

    def test_a_reinvocation_that_reads_a_correction_never_published_still_publishes_it(self) -> None:
        conductor = self._conductor("la senal no esta exenta", budgets=Budgets(person_wait_seconds=0))
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(
            kind=AlignmentResponseKind.REVIEW, correction="ademas falta un criterio"
        )

        conductor.conduct()

        assert conductor.understanding.write.call_count == 1


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
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=0))
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
    def _conductor(*, dangling: tuple[SubIssue, ...], models: RoleModels | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.about_to_start(dangling=dangling), models=models)

    def test_a_dangling_subissue_whose_pull_request_merged_writes_its_durable_row_as_merged(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        recorded = conductor.metrics.record.call_args_list[0].args[0]
        assert (recorded.repo, recorded.slice_id, recorded.name, recorded.state, recorded.run) == (
            Conductor.REPO,
            dangling.slice_id.canonical,
            dangling.slice_id.name,
            RunState.MERGED,
            dangling.run,
        )

    def test_a_dangling_subissue_whose_pull_request_merged_writes_the_budgets_and_models_this_invocation_ran_with(
        self,
    ) -> None:
        dangling = SubIssueMother.dangling()
        models = RoleModels(understand="opus", implement="opus", verify="opus", catch_up="opus")
        conductor = self._conductor(dangling=(dangling,), models=models)

        conductor.conduct()

        recorded = conductor.metrics.record.call_args_list[0].args[0]
        assert (recorded.budgets, recorded.models) == (conductor.budgets, models)

    def test_a_dangling_subissue_whose_pull_request_merged_drops_the_label_it_still_carried(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        conductor.repository.remove_label.assert_any_call(
            repo=Conductor.REPO, issue=dangling.number, remove=dangling.label
        )

    def test_a_dangling_subissue_whose_pull_request_merged_clears_its_run_so_it_stops_being_dangling(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))

        conductor.conduct()

        conductor.repository.clear_run.assert_any_call(repo=Conductor.REPO, issue=dangling.number)

    def test_a_dangling_subissue_whose_pull_request_closed_without_merging_is_left_untouched(self) -> None:
        dangling = SubIssueMother.dangling()
        conductor = self._conductor(dangling=(dangling,))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.closed()

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
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.closed()

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
        assert (recorded.slice_id, recorded.state) == (dangling.slice_id.canonical, RunState.MERGED)

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

    def test_a_sibling_with_a_malformed_retry_comment_is_answered_with_what_it_is_missing_before_raising(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        malformed_sibling = SubIssueMother.blocked(IssueLabel.BLOCKED_CI_RED, RunMother.blocked_on_red_ci())
        malformed = RetryResponse(kind=RetryResponseKind.MALFORMED, reason=MalformedReason.MISSING_INSTRUCTION)
        error = self._unselectable(dangling=())
        error.malformed_retries = ((malformed_sibling, malformed),)
        conductor.select.execute.side_effect = error

        with pytest.raises(NoSliceLeftError):
            conductor.conduct()

        conductor.repository.write_malformed_response.assert_called_once_with(
            repo=Conductor.REPO, issue=malformed_sibling.number, reason=MalformedReason.MISSING_INSTRUCTION
        )

    def test_the_failure_after_reconciling_a_dangling_run_says_how_many_it_reconciled_before_giving_up(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=(SubIssueMother.dangling(),))

        with pytest.raises(NoSliceLeftError, match="reconciled 1"):
            conductor.conduct()

    def test_the_failure_with_nothing_dangling_says_it_reconciled_zero_before_giving_up(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=())

        with pytest.raises(NoSliceLeftError, match="reconciled 0"):
            conductor.conduct()

    def test_a_dangling_run_whose_pull_request_closed_without_merging_is_not_counted_as_reconciled(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start())
        conductor.select.execute.side_effect = self._unselectable(dangling=(SubIssueMother.dangling(),))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.closed()

        with pytest.raises(NoSliceLeftError, match="reconciled 0"):
            conductor.conduct()


class TestConductSliceReopeningABlockedRun:
    @staticmethod
    def _blocked_and_reopened(label: IssueLabel, blocked_run: Run, reopened_run: Run) -> tuple[Conductor, Run]:
        blocked = SubIssueMother.blocked(label, blocked_run)
        retry = RetryResponse(kind=RetryResponseKind.RETRY, instruction=_RETRY_INSTRUCTION)
        chosen = replace(SelectSliceResultMother.about_to_start(subissue=blocked), retry=retry)
        conductor = Conductor(chosen=chosen)
        reopened = replace(blocked, run=reopened_run, label=IssueLabel.IN_PROGRESS)
        conductor.reopen.execute.return_value = ReopenSliceResult(subissue=reopened, instruction=_RETRY_INSTRUCTION)

        return conductor, blocked.run or reopened_run

    def test_a_chosen_slice_carrying_a_retry_response_is_reopened_before_anything_is_conducted(self) -> None:
        conductor, _ = self._blocked_and_reopened(
            IssueLabel.BLOCKED_CONTROLS,
            RunMother.blocked_on_controls(),
            replace(RunMother.blocked_on_controls(), control_retries=0),
        )
        blocked = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        conductor.conduct()

        conductor.reopen.execute.assert_called_once_with(
            ReopenSliceParams(repo=Conductor.REPO, subissue=blocked, instruction=_RETRY_INSTRUCTION)
        )

    def test_a_slice_chosen_without_a_retry_response_is_never_sent_to_be_reopened(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()))

        conductor.conduct()

        assert conductor.reopen.execute.call_count == 0

    def test_the_run_that_resumes_is_the_one_reopen_slice_handed_back_not_the_stale_blocked_one(self) -> None:
        conductor, _ = self._blocked_and_reopened(
            IssueLabel.BLOCKED_VERIFY,
            RunMother.blocked_on_verify(),
            replace(RunMother.blocked_on_verify(), verify_retries=0),
        )
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing()),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        assert conductor.verify.execute.call_count == 2
        assert conductor.implement.execute.call_count == 1

    def test_the_retry_instruction_that_reopened_the_slice_travels_to_the_implementer(self) -> None:
        conductor, _ = self._blocked_and_reopened(
            IssueLabel.BLOCKED_VERIFY,
            RunMother.blocked_on_verify(),
            replace(RunMother.blocked_on_verify(), verify_retries=0),
        )
        conductor.verify.execute.side_effect = [
            VerificationMother.vetoing(VerdictMother.failing()),
            VerificationMother.passing(),
        ]

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].retry_instruction == _RETRY_INSTRUCTION

    def test_reopening_a_run_blocked_on_controls_names_the_next_round_after_the_ones_already_logged(self) -> None:
        conductor, _ = self._blocked_and_reopened(
            IssueLabel.BLOCKED_CONTROLS,
            RunMother.blocked_on_controls(),
            replace(RunMother.blocked_on_controls(), control_retries=0),
        )

        conductor.conduct()

        slice_dir = Conductor.LOGS / SubIssueMother.pending().slice_id.canonical
        assert conductor.controls.run.call_args.kwargs["out"] == slice_dir / "round-4"

    def test_a_fresh_invocation_resuming_a_run_reopened_by_an_earlier_one_still_names_the_round_after_the_ones_logged(
        self,
    ) -> None:
        reopened_run = replace(RunMother.blocked_on_controls(), control_retries=0)
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(reopened_run))

        conductor.conduct()

        slice_dir = Conductor.LOGS / SubIssueMother.pending().slice_id.canonical
        assert conductor.controls.run.call_args_list[0].kwargs["out"] == slice_dir / "round-4"


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

        assert (result.halt, result.precheck) == (
            Halt.PRECHECKS_BLOCKED,
            PrecheckResult(outcome=PrecheckOutcome.SLICE_IN_ANOTHER_REPO),
        )
        assert conductor.verify.execute.call_count == 0
        assert conductor.repository.write_precheck_reason.call_count == 0

    def test_a_run_that_resumes_stops_before_implementing_when_its_declared_branch_no_longer_exists(self) -> None:
        conductor = self._conductor()
        conductor.branches.exists.return_value = False

        with pytest.raises(MissingBranchError, match=f"resumes expecting the branch `{_BRANCH}`.*no such branch"):
            conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert conductor.verify.execute.call_count == 0
        assert conductor.repository.write_run.call_count == 0

    def test_a_run_whose_understanding_was_already_published_recreates_the_branch_without_asking_the_harness_again(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.understanding_after_a_discard(HarnessSpendMother.of_the_understanding_call())
            )
        )
        conductor.branches.exists.return_value = False
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.GO)

        conductor.conduct()

        assert conductor.prechecks.execute.call_count == 0
        assert conductor.branches.create.call_count == 1
        assert conductor.understanding.write.call_count == 0
        assert conductor.implement.execute.call_count == 1

    def test_a_run_whose_understanding_is_still_pending_publishes_it_even_with_the_branch_missing(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_publish_the_understanding()))
        conductor.branches.exists.return_value = False
        conductor.repository.read_alignment_response.return_value = AlignmentResponse(kind=AlignmentResponseKind.GO)

        conductor.conduct()

        assert conductor.prechecks.execute.call_count == 1
        assert conductor.branches.create.call_count == 1
        assert conductor.understanding.write.call_count == 1
        assert conductor.implement.execute.call_count == 1


class TestConductSliceResumingCatchesUpTheBranch:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()))

    def test_a_branch_already_caught_up_still_reaches_the_implementer(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.implement.execute.call_count == 1

    def test_an_unresolvable_conflict_closes_the_run_without_ever_reaching_the_implementer_or_the_judge(self) -> None:
        conductor = self._conductor()
        conductor.branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=("shared.txt",)
        )
        conductor.branches.has_leftover_conflict_markers.return_value = True

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_CI_CONFLICT
        assert (conductor.implement.execute.call_count, conductor.verify.execute.call_count) == (0, 0)

    def test_an_unresolvable_conflict_writes_the_conflict_label_and_records_the_closed_row(self) -> None:
        conductor = self._conductor()
        conductor.branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=("shared.txt",)
        )
        conductor.branches.has_leftover_conflict_markers.return_value = True

        conductor.conduct()

        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CI_CONFLICT
        )
        assert conductor.closed.state is RunState.BLOCKED_CI_CONFLICT
        assert conductor.closed.conflict_block_cause is ConflictBlockCause.TREE_STILL_CONFLICTED

    def test_a_branch_that_no_longer_exists_is_never_asked_to_catch_up(self) -> None:
        conductor = self._conductor()
        conductor.branches.exists.return_value = False

        with pytest.raises(MissingBranchError):
            conductor.conduct()

        assert conductor.branches.catch_up.call_count == 0

    def test_a_run_already_awaiting_the_ci_of_a_pull_request_already_open_is_never_asked_to_catch_up(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()))

        conductor.conduct()

        assert conductor.branches.catch_up.call_count == 0

    def test_a_run_already_awaiting_the_merge_of_a_pull_request_already_open_is_never_asked_to_catch_up(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()))

        conductor.conduct()

        assert conductor.branches.catch_up.call_count == 0

    def test_a_run_already_at_the_catch_up_step_is_never_pre_checked_before_conducting(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.at_catch_up()))

        conductor.conduct()

        assert conductor.branches.catch_up.call_count == 1


class TestConductSliceResolvesAConflictAtTheCatchUpStep:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.at_catch_up()), budgets=budgets)

    def test_a_clean_catch_up_never_calls_the_resolver(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.resolver.resolve.call_count == 0

    def test_a_conflicting_catch_up_calls_the_resolver_exactly_once(self) -> None:
        conductor = self._conductor()
        conductor.branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=("shared.txt",)
        )

        conductor.conduct()

        assert conductor.resolver.resolve.call_count == 1

    def test_a_conflict_the_resolver_fixed_moves_on_to_run_the_controls(self) -> None:
        conductor = self._conductor()
        conductor.branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=("shared.txt",)
        )

        result = conductor.conduct()

        assert (result.state, result.step) == (RunState.MERGED, Step.AWAIT_MERGE)

    def test_a_tree_still_conflicted_after_the_resolver_retries_until_the_budget_is_spent(self) -> None:
        conductor = self._conductor(budgets=Budgets(catch_up_retries=2))
        conductor.branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=("shared.txt",)
        )
        conductor.branches.has_leftover_conflict_markers.return_value = True

        result = conductor.conduct()

        assert conductor.branches.catch_up.call_count == 3
        assert result.state is RunState.BLOCKED_CI_CONFLICT

    def test_a_tree_still_conflicted_once_the_budget_is_spent_names_the_tree_as_the_cause(self) -> None:
        conductor = self._conductor(budgets=Budgets(catch_up_retries=1))
        conductor.branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=("shared.txt",)
        )
        conductor.branches.has_leftover_conflict_markers.return_value = True

        conductor.conduct()

        assert conductor.closed.conflict_block_cause is ConflictBlockCause.TREE_STILL_CONFLICTED

    def test_the_resolver_touching_a_file_outside_the_conflict_also_retries_until_the_budget_is_spent(self) -> None:
        conductor = self._conductor(budgets=Budgets(catch_up_retries=1))
        conductor.branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=("shared.txt",)
        )
        conductor.branches.paths_touched_since_the_merge_attempt.return_value = ("shared.txt", "clean.txt")

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_CI_CONFLICT

    def test_a_resolver_call_that_dies_is_discarded_and_retried_instead_of_killing_the_run(self) -> None:
        conductor = self._conductor()
        conductor.branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=("shared.txt",)
        )
        died = InvalidResolutionReportError("the resolver's report could not be parsed")
        died.spend = HarnessSpendMother.of_the_catch_up_call()
        conductor.resolver.resolve.side_effect = [died, conductor.resolver.resolve.return_value]

        result = conductor.conduct()

        assert conductor.resolver.resolve.call_count == 2
        assert result.state is RunState.MERGED

    def test_controls_failing_after_resolving_a_conflict_closes_immediately_instead_of_repaying_the_implementer(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.at_catch_up_having_resolved_a_conflict())
        )
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert result.state is RunState.BLOCKED_CI_CONFLICT

    def test_controls_failing_after_resolving_a_conflict_names_the_controls_as_the_cause(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.at_catch_up_having_resolved_a_conflict())
        )
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        conductor.conduct()

        assert conductor.closed.conflict_block_cause is ConflictBlockCause.CONTROLS_FAILED

    def test_controls_failing_after_the_implementer_worked_again_following_a_resumed_catch_up_spends_a_mechanical_retry(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets(control_retries=0)
        )
        conductor.branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=("shared.txt",)
        )
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert result.state is RunState.BLOCKED_CONTROLS


class _ResumedAwaitingTheCi:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()), budgets=budgets)


class TestConductSliceCatchesUpTheBranchWhenTheCiFindsAConflict(_ResumedAwaitingTheCi):
    def test_a_conflict_found_by_the_ci_is_caught_up_instead_of_closing_the_run(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = conductor.conduct()

        assert conductor.branches.catch_up.call_count == 1
        assert (result.halt, result.state, result.step) == (Halt.WAIT_EXHAUSTED, RunState.OPEN, Step.AWAIT_CI)

    def test_the_round_trip_after_a_conflict_never_repays_the_implementer_or_the_judge(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        assert (conductor.implement.execute.call_count, conductor.verify.execute.call_count) == (0, 0)

    def test_the_delivery_that_reopens_the_pull_request_is_told_it_comes_from_a_catch_up(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        assert conductor.deliver.execute.call_args.args[0].from_catch_up is True

    def test_the_retry_that_returns_to_catch_up_waits_before_asking_the_ci_again(self) -> None:
        conductor = self._conductor(budgets=Budgets(catch_up_retries=1, seconds_between_ticks=45))
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        assert conductor.clock.sleep.call_args_list[0].kwargs["seconds"] == 45

    def test_the_catch_up_retries_exhausted_closes_the_run_as_a_conflict_just_like_before(self) -> None:
        conductor = self._conductor(budgets=Budgets(catch_up_retries=1))
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = conductor.conduct()

        assert conductor.branches.catch_up.call_count == 1
        assert result.state is RunState.BLOCKED_CI_CONFLICT

    def test_resuming_with_a_catch_up_retry_already_spent_does_not_reset_the_counter(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.with_one_catch_up_retry_already_spent()),
            budgets=Budgets(catch_up_retries=1),
        )
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = conductor.conduct()

        assert conductor.branches.catch_up.call_count == 0
        assert result.state is RunState.BLOCKED_CI_CONFLICT

    def test_a_control_round_that_fails_after_the_catch_up_still_sends_the_repaired_round_to_the_judge(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        conductor.conduct()

        assert conductor.verify.execute.call_count == 1

    def test_a_control_round_that_fails_after_the_catch_up_does_not_leave_the_next_delivery_skipping_its_commit(
        self,
    ) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
        conductor.ci.status.side_effect = [CiStatus.NO_CHECKS, CiStatus.PENDING]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()
        conductor.controls.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        conductor.conduct()

        assert conductor.deliver.execute.call_args.args[0].from_catch_up is False


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
        conductor.trace.calls_of.return_value = (
            HarnessCallMother.of_the_implementer(),
            HarnessCallMother.of_the_judge(),
        )
        conductor.seed_spend(session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=prior)
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )

        conductor.conduct()

        recorded: ClosedSlice = conductor.metrics.record.call_args.args[0]
        assert recorded.spend == HarnessSpend.summing((prior, HarnessSpendMother.of_the_judge_call()))

    def test_the_run_written_after_a_paid_call_persists_the_cumulative_spend_and_not_only_this_calls(self) -> None:
        prior = HarnessSpendMother.of_the_implementer_call()
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.judging_after_spending(prior)))

        conductor.conduct()

        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert written[0].spend == HarnessSpend.summing((prior, HarnessSpendMother.of_the_judge_call()))

    def test_the_closed_row_of_a_run_resumed_after_a_dead_invocation_counts_every_call_the_trace_holds(self) -> None:
        lost_to_the_dead_invocation = HarnessSpendMother.of_the_understanding_call()
        the_last_persisted = HarnessSpendMother.of_the_implementer_call()
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.judging_after_spending(the_last_persisted))
        )
        conductor.trace.calls_of.return_value = (
            HarnessCallMother.of_the_implementer(),
            HarnessCallMother.of_the_judge(),
        )
        conductor.seed_spend(session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=lost_to_the_dead_invocation)
        conductor.seed_spend(session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=the_last_persisted)

        conductor.conduct()

        recorded: ClosedSlice = conductor.metrics.record.call_args.args[0]
        assert recorded.run.spend == HarnessSpend.summing((the_last_persisted, HarnessSpendMother.of_the_judge_call()))
        assert recorded.spend == HarnessSpend.summing((lost_to_the_dead_invocation, the_last_persisted))


class TestConductSliceOnTheHappyPath:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_it_walks_the_steps_in_the_order_the_state_machine_dictates_and_persists_each_one(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30, person_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

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
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30, person_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

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

    def test_a_slice_carrying_a_user_story_reaches_the_judge_and_the_durable_row_by_its_canonical_identifier(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.implementing(), subissue=SubIssueMother.carrying_a_user_story()
            )
        )

        conductor.conduct()

        assert conductor.verify.execute.call_args.args[0].slice_id == "PROJ-1234-05"
        assert conductor.closed.slice_id == "PROJ-1234-05"

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
        conductor.trace.calls_of.return_value = (
            HarnessCallMother.of_the_implementer(),
            HarnessCallMother.of_the_judge(),
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=HarnessSpendMother.of_the_implementer_call()
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )

        conductor.conduct()

        recorded = conductor.closed
        assert (recorded.repo, recorded.slice_id, recorded.name) == (
            Conductor.REPO,
            "slice-05",
            "prechecks-deterministas",
        )
        assert recorded.state is RunState.MERGED
        assert recorded.spend == HarnessSpend.summing(
            (HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call())
        )

    def test_the_durable_row_carries_the_budgets_and_the_models_this_invocation_ran_with(self) -> None:
        models = RoleModels(understand="opus", implement="opus", verify="opus", catch_up="opus")
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()),
            budgets=Budgets(slice_cost_usd=99.0),
            models=models,
        )

        conductor.conduct()

        recorded = conductor.closed
        assert (recorded.budgets, recorded.models) == (conductor.budgets, models)

    def test_the_durable_row_carries_how_much_the_verified_diff_changed(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        recorded = conductor.closed
        assert recorded.diff_stats == SliceDiffMother.STATS

    def test_the_durable_row_carries_what_the_implementer_declared_left_out_as_debt(self) -> None:
        conductor = self._conductor()
        conductor.implement.execute.return_value = ImplementationMother.with_debt()

        conductor.conduct()

        recorded = conductor.closed
        assert recorded.debt == ImplementationMother.with_debt().left_out

    def test_the_verification_asked_for_carries_the_subissue_number_and_not_the_parent_issue(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        asked = conductor.verify.execute.call_args.args[0]
        assert (asked.repo, asked.issue, asked.worktree) == (Conductor.REPO, _SUBISSUE, Conductor.WORKTREE)
        assert asked.issue != Conductor.ISSUE

    def test_the_verification_diffs_against_the_remote_of_the_declared_base_and_not_the_local_copy(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        asked = conductor.verify.execute.call_args.args[0]
        assert asked.base == f"origin/{Conductor.BASE}"

    def test_the_durable_row_carries_the_subissue_number_and_not_the_parent_issue(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        recorded = conductor.closed
        assert recorded.issue == _SUBISSUE
        assert recorded.issue != Conductor.ISSUE


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
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        conductor.conduct()

        emitted = conductor.emitted_events
        assert (emitted[-1].step, emitted[-1].status) == (Step.AWAIT_MERGE, EventStatus.AWAITING_PERSON)

    def test_a_pending_ci_reports_waiting_because_no_person_is_deciding_anything_yet(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()),
            budgets=Budgets(ci_wait_seconds=90),
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

    def test_a_merged_run_clears_its_persisted_run_so_the_next_invocation_does_not_see_it_as_dangling(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.repository.clear_run.assert_called_once_with(repo=Conductor.REPO, issue=_SUBISSUE)

    def test_a_close_that_does_not_merge_the_slice_asks_to_close_nothing(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets(hygiene_retries=0)
        )
        conductor.stage.execute.side_effect = DirtyIndexError("src/leftover.py (not-declared)")

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_HYGIENE
        assert conductor.close.execute.call_count == 0


class TestConductSliceImplementing:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_a_broken_implementation_call_is_discarded_and_retried_within_budget(self) -> None:
        conductor = self._conductor()
        conductor.implement.execute.side_effect = [
            RejectionMother.invalid_implementation_report(),
            ImplementationMother.of_two_paths(),
        ]
        conductor.trace.calls_of.return_value = (
            HarnessCallMother.of_the_discarded_implementer(),
            HarnessCallMother.of_the_implementer(),
            HarnessCallMother.of_the_judge(),
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_DISCARDED_IMPLEMENTER,
            spend=HarnessSpendMother.of_a_call_that_cost_nothing(),
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=HarnessSpendMother.of_the_implementer_call()
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )

        conductor.conduct()

        assert conductor.implement.execute.call_count == 2
        recorded = conductor.closed
        assert recorded.run.implement_discards == 1
        assert recorded.discarded_call is not None
        assert recorded.discarded_call.step is Step.IMPLEMENT
        assert recorded.discarded_call.cause is DiscardCause.FAILED_CALL
        assert recorded.spend == HarnessSpend.summing(
            (
                HarnessSpendMother.of_a_call_that_cost_nothing(),
                HarnessSpendMother.of_the_implementer_call(),
                HarnessSpendMother.of_the_judge_call(),
            )
        )

    def test_the_retry_after_a_broken_call_is_told_the_previous_call_died_and_the_flag_clears_once_it_delivers(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.implement.execute.side_effect = [
            RejectionMother.invalid_implementation_report(),
            ImplementationMother.of_two_paths(),
        ]

        conductor.conduct()

        first_round, retried = conductor.implement.execute.call_args_list
        assert first_round.args[0].previous_call_died is False
        assert retried.args[0].previous_call_died is True
        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert written[-1].previous_call_died is False

    def test_a_call_killed_from_outside_leaves_the_flag_on_even_though_the_run_closes_for_an_unmeasured_call(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.implement.execute.side_effect = RejectionMother.envelope_nobody_could_parse()

        result = conductor.conduct()

        assert result.state is RunState.ABORTED_UNMEASURED_CALL
        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert written[-1].previous_call_died is True


class TestConductSliceWhenTheControlsComeBackRed:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=budgets)

    def test_the_log_of_the_red_control_reaches_the_next_implementation_as_a_path(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=1))
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        conductor.conduct()

        retried = conductor.implement.execute.call_args_list[-1].args[0]
        assert retried.control_logs == (ControlOutcomeMother.LOG,)

    def test_resuming_a_run_with_rounds_already_logged_names_the_next_round_not_round_one(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.running_the_controls_with_one_round_already_logged())
        )

        conductor.conduct()

        assert conductor.controls.run.call_args_list[0].kwargs["out"] == (
            Conductor.LOGS / SubIssueMother.pending().slice_id.canonical / "round-2"
        )

    def test_the_exhausted_control_budget_closes_the_run_writes_its_label_and_records_the_row(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=0))
        conductor.controls.run.return_value = ControlOutcomeMother.red()

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_CONTROLS
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.BLOCKED_CONTROLS
        )
        assert conductor.metrics.record.call_args.args[0].state is RunState.BLOCKED_CONTROLS

    def test_a_repo_exempt_from_controls_goes_straight_to_the_judge(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(
                RunMother.running_the_controls(), parent=ParentIssueMother.with_exempt_controls()
            )
        )

        conductor.conduct()

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
        conductor.trace.calls_of.return_value = (
            HarnessCallMother.of_the_discarded_verdict(),
            HarnessCallMother.of_the_implementer(),
            HarnessCallMother.of_the_judge(),
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_DISCARDED_VERDICT,
            spend=HarnessSpendMother.of_a_call_that_cost_nothing(),
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_IMPLEMENTER, spend=HarnessSpendMother.of_the_implementer_call()
        )
        conductor.seed_spend(
            session=HarnessCallMother.SESSION_OF_THE_JUDGE, spend=HarnessSpendMother.of_the_judge_call()
        )

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert (recorded.run.verify_discards, recorded.run.verify_retries) == (1, 0)
        assert recorded.spend == HarnessSpend.summing(
            (
                HarnessSpendMother.of_a_call_that_cost_nothing(),
                HarnessSpendMother.of_the_implementer_call(),
                HarnessSpendMother.of_the_judge_call(),
            )
        )
        assert recorded.discarded_call.cause is DiscardCause.INCOHERENT_VERDICT

    def test_a_call_that_left_no_verdict_at_all_is_discarded_as_a_failed_call_and_not_as_an_incoherent_one(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.verify.execute.side_effect = [RejectionMother.denied_read(), VerificationMother.passing()]

        conductor.conduct()

        assert conductor.metrics.record.call_args.args[0].discarded_call.cause is DiscardCause.FAILED_CALL


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
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.state is RunState.ABORTED_BUDGET
        assert recorded.discarded_call is not None
        assert recorded.discarded_call.step is Step.VERIFY
        assert recorded.discarded_call.cause is DiscardCause.INCOHERENT_VERDICT

    def test_discard_after_discard_of_the_implementation_closes_the_run_and_writes_its_label(self) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets(slice_cost_usd=0.5)
        )
        conductor.implement.execute.side_effect = [
            RejectionMother.invalid_implementation_report(),
            RejectionMother.invalid_implementation_report(),
        ]

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 2
        assert result.state is RunState.ABORTED_BUDGET
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.IN_PROGRESS, add=IssueLabel.ABORTED_BUDGET
        )
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.state is RunState.ABORTED_BUDGET
        assert recorded.discarded_call is not None
        assert recorded.discarded_call.step is Step.IMPLEMENT
        assert recorded.discarded_call.cause is DiscardCause.FAILED_CALL

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
        assert result.state is RunState.ABORTED_UNMEASURED_CALL
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.discarded_call.step is Step.VERIFY
        assert recorded.discarded_call.cause is DiscardCause.FAILED_CALL

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
        assert result.state is RunState.ABORTED_UNMEASURED_CALL

    def test_an_unmeasured_implementation_call_closes_the_run_instead_of_spinning_for_a_cost_nobody_can_add_up(
        self,
    ) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.implementing()), budgets=Budgets())
        conductor.implement.execute.side_effect = [
            RejectionMother.envelope_nobody_could_parse(),
            ImplementationMother.of_two_paths(),
        ]

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert result.state is RunState.ABORTED_UNMEASURED_CALL

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
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.closed()

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


class TestConductSliceWhenAReviewAsksForAChangeOnThePullRequest:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None, run: Run | None = None) -> Conductor:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(run or RunMother.awaiting_merge()),
            budgets=budgets or Budgets(person_wait_seconds=30),
        )
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        return conductor

    def test_a_submitted_review_sends_the_slice_back_to_implement_instead_of_waiting_for_the_merge(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 1

    def test_the_body_and_every_line_comment_of_the_review_travel_together_in_the_order_they_were_written(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (
            PullRequestReviewMother.asking_for_a_change_with_a_body_and_several_comments(
                body="corrige el manejo de errores", asked="esta linea sobra", also="y de paso mira el nombre"
            ),
        )

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(
                body="corrige el manejo de errores",
                comments=(
                    PullRequestReviewCommentMother.anchored_to_a_line(body="esta linea sobra"),
                    PullRequestReviewCommentMother.anchored_to_a_line(body="y de paso mira el nombre", line=43),
                ),
            ),
        )

    def test_the_native_request_changes_gesture_asks_for_a_change_too_when_a_teammate_can_use_it(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (
            PullRequestReviewMother.requesting_changes(asked="usa el value object"),
        )

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(body="usa el value object"),
        )

    @pytest.mark.parametrize(
        "review",
        [
            PullRequestReviewMother.approving(),
            PullRequestReviewMother.still_a_draft(),
            PullRequestReviewMother.dismissed(),
        ],
    )
    def test_a_review_that_neither_approves_nor_is_submitted_never_sends_the_slice_back_to_implement(
        self, review: PullRequestReview
    ) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (review,)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 0

    def test_the_judge_is_never_invoked_to_deliver_a_correction_that_only_answers_a_review(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        assert conductor.verify.execute.call_count == 0

    def test_the_correction_spends_neither_the_judge_nor_the_ci_retry_budget(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert written
        assert all((run.verify_retries, run.ci_retries) == (0, 0) for run in written)

    def test_several_changes_requested_reviews_are_delivered_in_a_single_round_in_the_order_they_were_sent(
        self,
    ) -> None:
        first = PullRequestReviewMother.asking_for_a_change(review_id=101, asked="arregla A")
        second = PullRequestReviewMother.asking_for_a_change(review_id=102, asked="arregla B")
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (first, second)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 1
        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(body="arregla A"),
            RequestedChange(body="arregla B"),
        )

    def test_the_body_of_the_review_reaches_the_implementer_in_the_round_it_triggers(self) -> None:
        asked = "usa el value object en vez del dict"
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(asked=asked),)

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (RequestedChange(body=asked),)

    def test_reinvoking_after_the_marker_advanced_does_not_reprocess_the_same_review(self) -> None:
        conductor = self._conductor(run=RunMother.awaiting_merge_after_reviewing(101))
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(review_id=101),)

        conductor.conduct()

        assert conductor.implement.execute.call_count == 0

    def test_the_marker_is_remembered_across_invocations_so_a_later_invocation_does_not_repeat_it(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(review_id=101),)

        conductor.conduct()

        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert any(run.last_reviewed_id == 101 for run in written)

    def test_the_correction_delivers_again_reusing_the_pull_request_already_open_for_the_slice(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        assert conductor.deliver.execute.call_count == 1
        assert conductor.deliver.execute.call_args.args[0].branch == _BRANCH

    def test_the_text_of_the_review_is_persisted_with_its_marker_so_a_dead_invocation_does_not_swallow_it(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(asked="arregla el borde"),)

        conductor.conduct()

        written = [call.kwargs["run"] for call in conductor.repository.write_run.call_args_list]
        assert (RequestedChange(body="arregla el borde"),) in [run.requested_changes for run in written]

    def test_an_invocation_resumed_mid_correction_reaches_the_implementer_with_the_review_it_had_to_attend(
        self,
    ) -> None:
        conductor = self._conductor(run=RunMother.correcting_a_review("arregla el borde"))

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(body="arregla el borde"),
        )

    def test_an_invocation_resumed_mid_correction_still_carries_the_anchored_comments_file_and_line(self) -> None:
        conductor = self._conductor(run=RunMother.correcting_a_review_with_an_anchored_comment())

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].requested_changes == (
            RequestedChange(body="", comments=(PullRequestReviewCommentMother.anchored_to_a_line(),)),
        )

    def test_delivering_the_correction_clears_the_review_so_the_next_round_is_judged_again(self) -> None:
        conductor = self._conductor()
        conductor.forum.reviews.return_value = (PullRequestReviewMother.asking_for_a_change(),)

        conductor.conduct()

        delivered = [
            call.kwargs["run"]
            for call in conductor.repository.write_run.call_args_list
            if call.kwargs["run"].step is Step.OPEN_PULL_REQUEST
        ]
        assert delivered
        assert all(run.requested_changes == () for run in delivered)


class TestConductSliceWaitingForTheMerge:
    @staticmethod
    def _conductor(*, budgets: Budgets | None = None) -> Conductor:
        return Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.awaiting_merge()), budgets=budgets)

    def test_a_merge_that_never_arrives_flags_the_subissue_that_its_pull_request_was_left_unmerged(self) -> None:
        conductor = self._conductor(budgets=Budgets(person_wait_seconds=30))
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        result = conductor.conduct()

        assert result.halt is Halt.WAIT_EXHAUSTED
        conductor.repository.flag_unmerged_pull_request.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, pull_request=Conductor.PULL_REQUEST
        )

    def test_a_ci_wait_that_is_exhausted_flags_nothing_because_the_pull_request_is_not_awaiting_a_merge_yet(
        self,
    ) -> None:
        conductor = Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()),
            budgets=Budgets(ci_wait_seconds=30),
        )
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        assert conductor.repository.flag_unmerged_pull_request.call_count == 0


class TestConductSliceWaitingForTheCi(_ResumedAwaitingTheCi):
    def test_a_pending_ci_ticks_with_the_separation_the_budget_declares_until_the_total_wait_is_spent(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=90))
        conductor.ci.status.return_value = CiStatus.PENDING

        result = conductor.conduct()

        assert [call.kwargs["seconds"] for call in conductor.clock.sleep.call_args_list] == [30, 30, 30]
        assert (result.halt, result.state, result.step) == (Halt.WAIT_EXHAUSTED, RunState.OPEN, Step.AWAIT_CI)

    def test_a_hung_ci_runs_out_on_its_own_cap_however_long_a_person_is_allowed_to_take(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=60, person_wait_seconds=86400))
        conductor.ci.status.return_value = CiStatus.PENDING

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == 2
        assert (result.halt, result.step) == (Halt.WAIT_EXHAUSTED, Step.AWAIT_CI)

    def test_what_the_ci_took_is_not_charged_to_the_person_who_has_to_merge(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=60, person_wait_seconds=60))
        conductor.ci.status.side_effect = [CiStatus.PENDING, CiStatus.GREEN]
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == 3
        assert (result.halt, result.step) == (Halt.WAIT_EXHAUSTED, Step.AWAIT_MERGE)

    def test_a_tick_that_changes_nothing_does_not_rewrite_the_state_of_the_run(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
        conductor.ci.status.return_value = CiStatus.PENDING

        conductor.conduct()

        assert conductor.repository.write_run.call_count == 0

    def test_an_invocation_that_ends_without_closing_the_run_writes_no_durable_row(self) -> None:
        conductor = self._conductor(budgets=Budgets(ci_wait_seconds=30))
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

        assert conductor.clock.sleep.call_count == Budgets().indeterminate_ticks - 1
        assert result.state is RunState.BLOCKED_CI_INDETERMINATE
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            remove=IssueLabel.IN_PROGRESS,
            add=IssueLabel.BLOCKED_CI_INDETERMINATE,
        )

    def test_a_conflicting_pull_request_with_no_checks_spends_its_own_retry_budget_not_the_indeterminate_window(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == Budgets().catch_up_retries
        assert result.state is RunState.BLOCKED_CI_CONFLICT
        conductor.repository.write_label.assert_called_once_with(
            repo=Conductor.REPO,
            issue=_SUBISSUE,
            remove=IssueLabel.IN_PROGRESS,
            add=IssueLabel.BLOCKED_CI_CONFLICT,
        )

    def test_a_conflicting_pull_request_that_closes_is_left_open_because_the_fix_is_merging_the_base(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        assert conductor.close.execute.call_count == 0

    def test_a_mergeable_pull_request_with_no_checks_still_spends_the_whole_grace_window(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_mergeable()

        result = conductor.conduct()

        assert conductor.clock.sleep.call_count == Budgets().indeterminate_ticks - 1
        assert result.state is RunState.BLOCKED_CI_INDETERMINATE

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


class TestConductSliceReusesTheSamePullRequestStatusReadForTheCiAndTheMerge(_ResumedAwaitingTheCi):
    def test_a_green_ci_asks_about_the_pull_request_only_once_to_poll_the_merge_and_not_to_check_a_conflict(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.GREEN

        conductor.conduct()

        assert conductor.forum.pull_request_state.call_count == 1


class TestConductSliceWhenTheCiCannotBeRead:
    @staticmethod
    def _conductor() -> Conductor:
        return Conductor(
            chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()),
            budgets=Budgets(indeterminate_ticks=0),
        )

    def test_the_command_itself_failing_still_closes_as_indeterminate_and_not_as_a_crash(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.side_effect = CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited")

        result = conductor.conduct()

        assert result.state is RunState.BLOCKED_CI_INDETERMINATE

    def test_the_command_itself_failing_records_that_concrete_cause_on_the_durable_row(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.side_effect = CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited")

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is CiIndeterminateCause.COMMAND_FAILED

    def test_a_response_that_arrived_but_could_not_be_read_records_a_different_cause_than_a_failed_command(
        self,
    ) -> None:
        conductor = self._conductor()
        conductor.ci.status.side_effect = UnreadableCiError("gh did not return JSON: not valid")

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is CiIndeterminateCause.UNREADABLE_RESPONSE

    def test_a_legitimate_no_checks_reading_leaves_the_cause_out_because_nothing_failed(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.return_value = CiStatus.NO_CHECKS

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is None

    def test_a_failed_command_against_a_conflicting_pull_request_records_no_indeterminate_cause(self) -> None:
        conductor = self._conductor()
        conductor.ci.status.side_effect = CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited")
        conductor.forum.pull_request_state.return_value = PullRequestStatusMother.open_and_conflicting()

        conductor.conduct()

        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is None

    def test_a_cause_recorded_on_an_earlier_tick_survives_a_later_tick_that_reads_the_ci_cleanly(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.resumed_at(RunMother.about_to_ask_the_ci()))
        conductor.ci.status.side_effect = [
            CiCommandFailedError("gh pr checks failed for owner/repo#61: rate limited"),
            CiStatus.GREEN,
        ]

        result = conductor.conduct()

        assert result.state is RunState.MERGED
        recorded = conductor.metrics.record.call_args.args[0]
        assert recorded.ci_indeterminate_cause is CiIndeterminateCause.COMMAND_FAILED
