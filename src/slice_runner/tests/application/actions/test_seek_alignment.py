from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.seek_alignment import SeekAlignment, SeekAlignmentParams
from slice_runner.domain.alignment import Alignment
from slice_runner.domain.alignment_stage import AlignmentStage
from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.understanding_writer import UnderstandingWriter
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.understanding_mother import UnderstandingMother

if TYPE_CHECKING:
    from slice_runner.domain.run import Run

_REPO = "alcaptar/agentic-skills"
_WORKTREE = "/repos/agentic-skills"
_ISSUE = SubIssueMother.pending().number


class TestSeekAlignment:
    @pytest.fixture
    def understanding(self) -> Mock:
        writer: Mock = create_autospec(UnderstandingWriter, spec_set=True, instance=True)
        writer.write.return_value = UnderstandingMother.of_the_chosen_slice()
        return writer

    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        repository.read_understanding.return_value = UnderstandingMother.TEXT
        return repository

    @pytest.fixture
    def action(self, understanding: Mock, repository: Mock) -> SeekAlignment:
        return SeekAlignment(understanding=understanding, repository=repository)

    @staticmethod
    def _params(*, run: Run, understanding: str = "") -> SeekAlignmentParams:
        return SeekAlignmentParams(
            repo=_REPO,
            worktree=_WORKTREE,
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            run=run,
            understanding=understanding,
        )

    def test_a_run_to_draft_publishes_the_understanding_with_no_agreement_and_no_correction_yet(
        self, action: SeekAlignment, understanding: Mock
    ) -> None:
        action.execute(self._params(run=RunMother.about_to_publish_the_understanding()))

        understanding.write.assert_called_once_with(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=_REPO,
            worktree=_WORKTREE,
            alignment=Alignment(),
        )

    def test_a_run_to_draft_writes_the_run_before_writing_the_understanding_comment(
        self, action: SeekAlignment, repository: Mock
    ) -> None:
        manager = Mock()
        manager.attach_mock(repository.write_run, "write_run")
        manager.attach_mock(repository.write_understanding, "write_understanding")

        action.execute(self._params(run=RunMother.about_to_publish_the_understanding()))

        assert [call[0] for call in manager.mock_calls] == ["write_run", "write_understanding"]

    def test_a_run_to_draft_persists_a_run_now_awaiting_carrying_the_spend_of_the_call(
        self, action: SeekAlignment, repository: Mock
    ) -> None:
        action.execute(self._params(run=RunMother.about_to_publish_the_understanding()))

        repository.write_run.assert_called_once_with(
            repo=_REPO,
            issue=_ISSUE,
            run=RunMother.awaiting_alignment_after_spending(HarnessSpendMother.of_the_understanding_call()),
        )
        repository.write_understanding.assert_called_once_with(
            repo=_REPO, issue=_ISSUE, understanding=UnderstandingMother.TEXT
        )

    def test_a_run_to_draft_returns_the_run_and_the_understanding_that_were_just_published(
        self, action: SeekAlignment
    ) -> None:
        result = action.execute(self._params(run=RunMother.about_to_publish_the_understanding()))

        assert (result.run, result.understanding, result.response) == (
            RunMother.awaiting_alignment_after_spending(HarnessSpendMother.of_the_understanding_call()),
            UnderstandingMother.TEXT,
            AlignmentStage.AWAITING,
        )

    def test_a_rejected_publication_propagates_instead_of_being_swallowed(
        self, action: SeekAlignment, understanding: Mock
    ) -> None:
        understanding.write.side_effect = InvalidUnderstandingReportError("blank text")

        with pytest.raises(InvalidUnderstandingReportError, match="blank text"):
            action.execute(self._params(run=RunMother.about_to_publish_the_understanding()))

    def test_a_run_awaiting_the_person_neither_publishes_again_nor_touches_the_issue(
        self, action: SeekAlignment, repository: Mock, understanding: Mock
    ) -> None:
        result = action.execute(self._params(run=RunMother.awaiting_alignment()))

        assert understanding.write.call_count == 0
        assert repository.mock_calls == []
        assert (result.run, result.response) == (RunMother.awaiting_alignment(), AlignmentStage.AWAITING)

    def test_a_run_with_the_understanding_agreed_neither_publishes_nor_touches_the_issue(
        self, action: SeekAlignment, repository: Mock, understanding: Mock
    ) -> None:
        result = action.execute(self._params(run=RunMother.with_the_understanding_agreed()))

        assert understanding.write.call_count == 0
        assert repository.mock_calls == []
        assert (result.run, result.response) == (RunMother.with_the_understanding_agreed(), AlignmentStage.AGREED)

    def test_a_run_to_redraft_after_a_correction_rewrites_the_understanding_with_it(
        self, action: SeekAlignment, understanding: Mock
    ) -> None:
        action.execute(
            self._params(
                run=RunMother.about_to_redraft_after_a_correction("la senal no esta exenta"),
                understanding=UnderstandingMother.TEXT,
            )
        )

        understanding.write.assert_called_once_with(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=_REPO,
            worktree=_WORKTREE,
            alignment=Alignment(agreed=UnderstandingMother.TEXT, correction="la senal no esta exenta"),
        )

    def test_a_redraft_seeds_the_agreed_text_from_the_repository_only_when_none_was_cached(
        self, action: SeekAlignment, repository: Mock, understanding: Mock
    ) -> None:
        action.execute(
            self._params(run=RunMother.about_to_redraft_after_a_correction("la senal no esta exenta"), understanding="")
        )

        repository.read_understanding.assert_called_once_with(repo=_REPO, issue=_ISSUE)
        understanding.write.assert_called_once_with(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=_REPO,
            worktree=_WORKTREE,
            alignment=Alignment(agreed=UnderstandingMother.TEXT, correction="la senal no esta exenta"),
        )

    def test_a_redraft_does_not_reread_the_agreed_text_when_it_is_already_cached(
        self, action: SeekAlignment, repository: Mock, understanding: Mock
    ) -> None:
        action.execute(
            self._params(
                run=RunMother.about_to_redraft_after_a_correction("la senal no esta exenta"),
                understanding="ya en cache",
            )
        )

        assert repository.read_understanding.call_count == 0
        understanding.write.assert_called_once_with(
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            repo=_REPO,
            worktree=_WORKTREE,
            alignment=Alignment(agreed="ya en cache", correction="la senal no esta exenta"),
        )

    def test_a_redraft_carries_the_spend_forward_on_top_of_what_was_already_spent(self, action: SeekAlignment) -> None:
        already_spent = HarnessSpendMother.of_the_understanding_call()
        pending = replace(RunMother.about_to_redraft_after_a_correction("la senal no esta exenta"), spend=already_spent)

        result = action.execute(self._params(run=pending, understanding=UnderstandingMother.TEXT))

        assert result.run.spend == already_spent.plus(HarnessSpendMother.of_the_understanding_call())

    def test_a_rejected_redraft_propagates_instead_of_being_swallowed(
        self, action: SeekAlignment, understanding: Mock
    ) -> None:
        understanding.write.side_effect = InvalidUnderstandingReportError("blank text")

        with pytest.raises(InvalidUnderstandingReportError, match="blank text"):
            action.execute(
                self._params(
                    run=RunMother.about_to_redraft_after_a_correction("la senal no esta exenta"),
                    understanding=UnderstandingMother.TEXT,
                )
            )
