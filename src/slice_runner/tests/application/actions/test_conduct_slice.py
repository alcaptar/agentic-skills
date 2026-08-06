from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.budgets import Budgets
from slice_runner.domain.ci_status import CiStatus
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.exceptions import DirtyIndexError, NoPullRequestError
from slice_runner.domain.halt import Halt
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.pull_request_state import PullRequestState
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
    from unittest.mock import Mock

    from slice_runner.domain.closed_slice import ClosedSlice

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

    def test_the_invocation_that_asks_for_alignment_writes_no_code_at_all(self) -> None:
        conductor = self._conductor()

        result = conductor.conduct()

        assert conductor.implement.execute.call_count == 0
        assert result.halt is Halt.AWAITING_ALIGNMENT

    def test_the_run_pauses_on_the_label_the_subissue_already_carried(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.repository.pause_for_alignment.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=IssueLabel.PENDING
        )

    def test_a_subissue_with_no_label_yet_pauses_without_asking_gh_to_remove_one_that_is_not_there(self) -> None:
        conductor = Conductor(chosen=SelectSliceResultMother.about_to_start(subissue=SubIssueMother.unlabelled()))

        conductor.conduct()

        conductor.repository.pause_for_alignment.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, remove=None
        )

    def test_the_branch_of_the_slice_is_cut_from_the_declared_base(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.branches.create.assert_called_once_with(
            worktree=Conductor.WORKTREE, name=_BRANCH, base=Conductor.BASE
        )

    def test_the_run_is_persisted_at_implement_so_the_next_invocation_resumes_instead_of_starting_over(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        conductor.repository.write_run.assert_called_once_with(
            repo=Conductor.REPO, issue=_SUBISSUE, run=RunMother.implementing()
        )

    def test_a_pause_that_never_lands_persists_no_run_so_the_next_invocation_cannot_skip_the_gate(self) -> None:
        conductor = self._conductor()
        conductor.repository.pause_for_alignment.side_effect = OSError("gh: rate limited")

        with pytest.raises(OSError, match="rate limited"):
            conductor.conduct()

        assert conductor.repository.write_run.call_count == 0
        assert conductor.branches.create.call_count == 0

    def test_an_understanding_that_never_lands_persists_no_run_because_nobody_could_answer_it(self) -> None:
        conductor = self._conductor()
        conductor.repository.write_understanding.side_effect = OSError("gh: rate limited")

        with pytest.raises(OSError, match="rate limited"):
            conductor.conduct()

        assert conductor.repository.write_run.call_count == 0
        assert conductor.repository.pause_for_alignment.call_count == 0

    def test_a_precheck_that_is_not_clear_ends_the_invocation_without_branching_or_writing_anything(self) -> None:
        conductor = self._conductor()
        conductor.prechecks.execute.return_value = PrecheckOutcome.BRANCH_ALREADY_EXISTS

        result = conductor.conduct()

        assert (result.halt, result.precheck) == (Halt.PRECHECKS_BLOCKED, PrecheckOutcome.BRANCH_ALREADY_EXISTS)
        assert conductor.branches.create.call_count == 0
        assert conductor.repository.write_understanding.call_count == 0
        assert conductor.repository.write_run.call_count == 0


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

    def test_the_controls_are_run_in_the_worktree_and_leave_their_log_where_the_invocation_asked(self) -> None:
        conductor = self._conductor()

        conductor.conduct()

        assert conductor.controls.run.call_args.kwargs == {"repo": Conductor.WORKTREE, "out": Conductor.LOGS}

    def test_a_dirty_index_fails_the_step_without_running_a_single_control(self) -> None:
        conductor = self._conductor(budgets=Budgets(control_retries=0))
        conductor.stage.execute.side_effect = DirtyIndexError("the staged index is not what the implementer reported")

        result = conductor.conduct()

        assert conductor.controls.run.call_count == 0
        assert result.state is RunState.BLOCKED_CONTROLS

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
        conductor = self._conductor(budgets=Budgets(verify_retries=1))
        conductor.verify.execute.return_value = VerificationMother.ordering_corrections(raised)

        conductor.conduct()

        assert conductor.implement.execute.call_args.args[0].findings == (raised,)
        assert conductor.deliver.execute.call_count == 1

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
