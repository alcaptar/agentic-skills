from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.agree_understanding import AgreeUnderstanding, AgreeUnderstandingParams
from slice_runner.domain.exceptions import OrderRefusedError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.order import Order
from slice_runner.domain.run_repository import RunRepository
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.sub_issue import SubIssue

_REPO = "alcaptar/agentic-skills"


class TestAgreeUnderstanding:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)

        return repository

    @pytest.fixture
    def action(self, repository: Mock) -> AgreeUnderstanding:
        return AgreeUnderstanding(repository=repository)

    def test_the_run_is_persisted_with_the_understanding_agreed(
        self, action: AgreeUnderstanding, repository: Mock
    ) -> None:
        subissue = SubIssueMother.awaiting_alignment()

        action.execute(AgreeUnderstandingParams(repo=_REPO, subissue=subissue))

        repository.write_run.assert_called_once_with(
            repo=_REPO, issue=subissue.number, run=RunMother.with_the_understanding_agreed()
        )

    def test_the_order_is_left_on_the_subissue_without_text(self, action: AgreeUnderstanding, repository: Mock) -> None:
        subissue = SubIssueMother.awaiting_alignment()

        action.execute(AgreeUnderstandingParams(repo=_REPO, subissue=subissue))

        repository.mark_order.assert_called_once_with(repo=_REPO, issue=subissue.number, order=Order.GO, text="")

    @pytest.mark.parametrize(
        "subissue",
        [
            SubIssueMother.pending(),
            SubIssueMother.closed(),
            SubIssueMother.redrafting_after_a_correction("otra cosa"),
            SubIssueMother.awaiting_alignment_with_the_understanding_agreed(),
            SubIssueMother.blocked(IssueLabel.BLOCKED_CONTROLS, RunMother.blocked_on_controls()),
        ],
    )
    def test_a_slice_that_is_not_waiting_for_alignment_is_refused_before_writing_anything(
        self, action: AgreeUnderstanding, repository: Mock, subissue: SubIssue
    ) -> None:
        with pytest.raises(OrderRefusedError, match="#45"):
            action.execute(AgreeUnderstandingParams(repo=_REPO, subissue=subissue))

        repository.write_run.assert_not_called()
        repository.mark_order.assert_not_called()
        repository.write_label.assert_not_called()
