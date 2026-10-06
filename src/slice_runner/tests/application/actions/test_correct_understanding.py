from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.correct_understanding import CorrectUnderstanding, CorrectUnderstandingParams
from slice_runner.domain.exceptions import OrderRefusedError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.order import Order
from slice_runner.domain.run_repository import RunRepository
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.sub_issue import SubIssue

_REPO = "alcaptar/agentic-skills"
_CORRECTION = "falta el caso de la slice ya cerrada"
_OTHER_CORRECTION = "mejor: el caso de la slice ya cerrada y el de la abierta"


class TestCorrectUnderstanding:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)

        return repository

    @pytest.fixture
    def action(self, repository: Mock) -> CorrectUnderstanding:
        return CorrectUnderstanding(repository=repository)

    def test_the_correction_is_persisted_and_the_understanding_goes_back_to_being_drafted(
        self, action: CorrectUnderstanding, repository: Mock
    ) -> None:
        subissue = SubIssueMother.awaiting_alignment()

        action.execute(CorrectUnderstandingParams(repo=_REPO, subissue=subissue, correction=_CORRECTION))

        repository.write_run.assert_called_once_with(
            repo=_REPO, issue=subissue.number, run=RunMother.about_to_redraft_after_a_correction(_CORRECTION)
        )

    def test_a_second_correction_replaces_the_first_one(self, action: CorrectUnderstanding, repository: Mock) -> None:
        subissue = SubIssueMother.redrafting_after_a_correction(_CORRECTION)

        action.execute(CorrectUnderstandingParams(repo=_REPO, subissue=subissue, correction=_OTHER_CORRECTION))

        repository.write_run.assert_called_once_with(
            repo=_REPO, issue=subissue.number, run=RunMother.about_to_redraft_after_a_correction(_OTHER_CORRECTION)
        )

    def test_the_order_is_left_on_the_subissue_with_the_correction(
        self, action: CorrectUnderstanding, repository: Mock
    ) -> None:
        subissue = SubIssueMother.awaiting_alignment()

        action.execute(CorrectUnderstandingParams(repo=_REPO, subissue=subissue, correction=_CORRECTION))

        repository.mark_order.assert_called_once_with(
            repo=_REPO, issue=subissue.number, order=Order.REVIEW, text=_CORRECTION
        )

    @pytest.mark.parametrize(
        "subissue",
        [
            SubIssueMother.pending(),
            SubIssueMother.closed(),
            SubIssueMother.awaiting_alignment_with_the_understanding_agreed(),
            SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls()),
        ],
    )
    def test_a_slice_that_is_not_waiting_for_alignment_is_refused_before_writing_anything(
        self, action: CorrectUnderstanding, repository: Mock, subissue: SubIssue
    ) -> None:
        with pytest.raises(OrderRefusedError, match="#45"):
            action.execute(CorrectUnderstandingParams(repo=_REPO, subissue=subissue, correction=_CORRECTION))

        repository.write_run.assert_not_called()
        repository.mark_order.assert_not_called()
