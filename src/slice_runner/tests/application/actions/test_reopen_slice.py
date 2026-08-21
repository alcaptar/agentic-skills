from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.reopen_slice import ReopenSlice, ReopenSliceParams
from slice_runner.domain.budgets import Budgets
from slice_runner.domain.exceptions import ImpossibleTransitionError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.state_machine import StateMachine
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.run import Run

_REPO = "alcaptar/agentic-skills"
_INSTRUCTION = "el control ya esta arreglado a mano"

_BLOCKS: list[tuple[IssueLabel, Run, Run]] = [
    (
        IssueLabel.BLOCKED_CONTROLS,
        RunMother.blocked_on_controls(),
        replace(RunMother.blocked_on_controls(), control_retries=0),
    ),
    (
        IssueLabel.BLOCKED_HYGIENE,
        RunMother.blocked_on_hygiene(),
        replace(RunMother.blocked_on_hygiene(), hygiene_retries=0),
    ),
    (
        IssueLabel.BLOCKED_VERIFY,
        RunMother.blocked_on_verify(),
        replace(RunMother.blocked_on_verify(), verify_retries=0),
    ),
    (IssueLabel.BLOCKED_CI_RED, RunMother.blocked_on_red_ci(), replace(RunMother.blocked_on_red_ci(), ci_retries=0)),
    (
        IssueLabel.BLOCKED_CI_INDETERMINATE,
        RunMother.blocked_on_indeterminate_ci(),
        replace(RunMother.blocked_on_indeterminate_ci(), indeterminate_ticks=0),
    ),
    (
        IssueLabel.BLOCKED_CI_CONFLICT,
        RunMother.blocked_on_conflict(),
        replace(RunMother.blocked_on_conflict(), catch_up_retries=0),
    ),
    (
        IssueLabel.ABORTED_BUDGET,
        RunMother.aborted_for_budget(HarnessSpendMother.of_the_implementer_call()),
        replace(
            RunMother.aborted_for_budget(HarnessSpendMother.of_the_implementer_call()),
            spend=HarnessSpend.nothing(),
            spend_before_reopening=HarnessSpendMother.of_the_implementer_call(),
        ),
    ),
    (
        IssueLabel.ABORTED_UNMEASURED_CALL,
        RunMother.aborted_for_an_unmeasured_call(HarnessSpendMother.of_the_implementer_call()),
        RunMother.aborted_for_an_unmeasured_call(HarnessSpendMother.of_the_implementer_call()),
    ),
]


class TestReopenSlice:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)

        return repository

    @pytest.fixture
    def action(self, repository: Mock) -> ReopenSlice:
        return ReopenSlice(repository=repository, machine=StateMachine(budgets=Budgets()))

    @pytest.mark.parametrize(("label", "blocked_run", "reopened_run"), _BLOCKS)
    def test_the_budget_that_closed_the_run_is_the_only_one_restored(
        self, action: ReopenSlice, repository: Mock, label: IssueLabel, blocked_run: Run, reopened_run: Run
    ) -> None:
        subissue = SubIssueMother.blocked(label, blocked_run)

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.write_run.assert_called_once_with(repo=_REPO, issue=subissue.number, run=reopened_run)

    @pytest.mark.parametrize(("label", "blocked_run", "reopened_run"), _BLOCKS)
    def test_the_blocking_label_is_swapped_for_the_one_that_matches_the_resumed_step(
        self, action: ReopenSlice, repository: Mock, label: IssueLabel, blocked_run: Run, reopened_run: Run
    ) -> None:
        subissue = SubIssueMother.blocked(label, blocked_run)

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.write_label.assert_called_once_with(
            repo=_REPO, issue=subissue.number, remove=label, add=IssueLabel.IN_PROGRESS
        )

    def test_reopening_after_a_conflict_also_resets_the_indeterminate_ticks_piled_up_before_it(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        subissue = SubIssueMother.blocked(
            IssueLabel.BLOCKED_CI_CONFLICT, RunMother.blocked_on_conflict_with_indeterminate_ticks_piled_up()
        )

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.write_run.assert_called_once_with(
            repo=_REPO,
            issue=subissue.number,
            run=replace(
                RunMother.blocked_on_conflict_with_indeterminate_ticks_piled_up(),
                catch_up_retries=0,
                indeterminate_ticks=0,
            ),
        )

    def test_the_instruction_that_reopened_the_slice_is_left_on_the_subissue_marked_as_consumed(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        subissue = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.mark_reopened.assert_called_once_with(repo=_REPO, issue=subissue.number, instruction=_INSTRUCTION)

    def test_the_result_carries_the_reopened_subissue_and_the_instruction_that_reopened_it(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        subissue = SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls())

        result = action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        assert result.subissue == replace(
            subissue, run=replace(RunMother.blocked_on_controls(), control_retries=0), label=IssueLabel.IN_PROGRESS
        )
        assert result.instruction == _INSTRUCTION

    def test_reopening_a_run_blocked_for_budget_a_second_time_keeps_both_windows_instead_of_only_the_latest(
        self, action: ReopenSlice, repository: Mock
    ) -> None:
        first_window = HarnessSpendMother.of_the_understanding_call()
        second_window = HarnessSpendMother.of_the_implementer_call()
        blocked_run = RunMother.aborted_for_budget_after_a_prior_reopening(
            spend_before_reopening=first_window, spend=second_window
        )
        subissue = SubIssueMother.blocked(IssueLabel.ABORTED_BUDGET, blocked_run)

        action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

        repository.write_run.assert_called_once_with(
            repo=_REPO,
            issue=subissue.number,
            run=replace(
                blocked_run,
                spend=HarnessSpend.nothing(),
                spend_before_reopening=HarnessSpend.summing((first_window, second_window)),
            ),
        )

    def test_a_subissue_with_no_run_on_record_cannot_be_reopened(self, action: ReopenSlice) -> None:
        subissue = replace(
            SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls()), run=None
        )

        with pytest.raises(ImpossibleTransitionError, match=str(subissue.number)):
            action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))

    def test_a_subissue_carrying_no_label_cannot_be_reopened(self, action: ReopenSlice) -> None:
        subissue = replace(
            SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls()), label=None
        )

        with pytest.raises(ImpossibleTransitionError, match=str(subissue.number)):
            action.execute(ReopenSliceParams(repo=_REPO, subissue=subissue, instruction=_INSTRUCTION))
