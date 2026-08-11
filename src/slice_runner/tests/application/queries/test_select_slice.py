from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.select_slice import SelectSlice, SelectSliceParams
from slice_runner.domain.checklist_entry import ChecklistEntry
from slice_runner.domain.exceptions import NoSliceLeftError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.issue_state import IssueState
from slice_runner.domain.retry_response import RetryResponse
from slice_runner.domain.retry_response_kind import RetryResponseKind
from slice_runner.domain.run_repository import RunRepository
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

_INSTRUCTION = "el control ya esta arreglado a mano"

_REPO = "alcaptar/agentic-skills"
_ISSUE = 38

_PARAMS = SelectSliceParams(repo=_REPO, issue=_ISSUE)

_CLOSURES_OF_A_PREVIOUS_RUN = (
    IssueLabel.BLOCKED_CONTROLS,
    IssueLabel.BLOCKED_HYGIENE,
    IssueLabel.BLOCKED_VERIFY,
    IssueLabel.BLOCKED_CI_RED,
    IssueLabel.BLOCKED_CI_INDETERMINATE,
    IssueLabel.ABORTED_BUDGET,
)

_LABELS_THAT_DISQUALIFY_A_SLICE = _CLOSURES_OF_A_PREVIOUS_RUN

_LABELS_THAT_LEAVE_A_SLICE_RUNNABLE = tuple(
    label for label in IssueLabel if label not in _LABELS_THAT_DISQUALIFY_A_SLICE
)


class TestSelectSlice:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        repository.read_parent.side_effect = [
            ParentIssueMother.of_two_slices(),
            ParentIssueMother.with_exempt_controls(),
        ]
        repository.read_children.return_value = (SubIssueMother.closed(), SubIssueMother.of_another_repo())
        return repository

    @pytest.fixture
    def query(self, repository: Mock) -> SelectSlice:
        return SelectSlice(repository=repository)

    def test_the_slice_to_run_is_the_first_one_that_is_not_closed(self, query: SelectSlice) -> None:
        assert query.execute(_PARAMS).subissue == SubIssueMother.of_another_repo()

    def test_the_children_are_asked_for_with_the_count_the_parent_declared_so_a_lagging_index_is_visible(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        query.execute(_PARAMS)

        repository.read_children.assert_called_once_with(repo=_REPO, parent=_ISSUE, expected=2)

    def test_the_parent_is_read_again_scoped_to_the_repo_where_the_chosen_slice_lives(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        query.execute(_PARAMS)

        repository.read_parent.assert_called_with(repo=_REPO, issue=_ISSUE, slice_repo=SubIssueMother.OTHER_REPO)

    def test_the_sources_and_controls_that_come_back_are_the_ones_of_the_scoped_read(self, query: SelectSlice) -> None:
        assert query.execute(_PARAMS).parent == ParentIssueMother.with_exempt_controls()

    def test_the_checklist_carries_every_slice_of_the_issue_and_not_only_the_chosen_one(
        self, query: SelectSlice
    ) -> None:
        assert query.execute(_PARAMS).checklist == (
            ChecklistEntry(title=SubIssueMother.closed().title, state=IssueState.CLOSED),
            ChecklistEntry(title=SubIssueMother.of_another_repo().title, state=IssueState.OPEN),
        )

    def test_an_issue_with_every_slice_closed_raises_instead_of_handing_back_a_finished_one(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.closed(),)

        with pytest.raises(NoSliceLeftError, match=str(_ISSUE)):
            query.execute(_PARAMS)

    def test_an_issue_with_every_slice_closed_still_carries_what_was_left_dangling_among_its_siblings(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.dangling(),)

        with pytest.raises(NoSliceLeftError) as raised:
            query.execute(_PARAMS)

        assert raised.value.dangling == (SubIssueMother.dangling(),)

    def test_with_two_slices_runnable_the_one_that_comes_first_is_the_one_that_runs(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.pending(), SubIssueMother.of_another_repo())

        assert query.execute(_PARAMS).subissue == SubIssueMother.pending()

    def test_a_slice_a_previous_run_left_blocked_is_skipped_instead_of_chosen_again(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (
            SubIssueMother.carrying(IssueLabel.BLOCKED_CI_RED),
            SubIssueMother.of_another_repo(),
        )

        assert query.execute(_PARAMS).subissue == SubIssueMother.of_another_repo()

    def test_a_blocked_slice_with_no_run_on_record_never_asks_the_forum_for_a_retry_instruction(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.carrying(IssueLabel.BLOCKED_CI_RED),)

        with pytest.raises(NoSliceLeftError):
            query.execute(_PARAMS)

        assert repository.read_retry_instruction.call_count == 0

    @pytest.mark.parametrize("label", _LABELS_THAT_DISQUALIFY_A_SLICE)
    def test_a_slice_a_previous_run_closed_or_blocked_is_never_picked_up_again_on_its_own(
        self, query: SelectSlice, repository: Mock, label: IssueLabel
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.carrying(label),)

        with pytest.raises(NoSliceLeftError, match=str(_ISSUE)):
            query.execute(_PARAMS)

    @pytest.mark.parametrize("label", _LABELS_THAT_LEAVE_A_SLICE_RUNNABLE)
    def test_every_other_label_of_the_vocabulary_leaves_the_slice_runnable_instead_of_falling_through(
        self, query: SelectSlice, repository: Mock, label: IssueLabel
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.carrying(label),)

        assert query.execute(_PARAMS).subissue.label is label

    def test_a_slice_that_carries_no_label_at_all_is_runnable_because_nothing_has_closed_it(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.unlabelled(),)

        assert query.execute(_PARAMS).subissue == SubIssueMother.unlabelled()

    def test_a_slice_that_lives_in_the_repo_of_its_issue_does_not_pay_a_second_read_of_the_parent(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.pending(),)

        chosen = query.execute(_PARAMS)

        repository.read_parent.assert_called_once_with(repo=_REPO, issue=_ISSUE, slice_repo=None)
        assert chosen.parent == ParentIssueMother.of_two_slices()

    def test_a_subissue_github_closed_while_its_run_was_still_open_surfaces_as_dangling(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.dangling(), SubIssueMother.pending())

        assert query.execute(_PARAMS).dangling == (SubIssueMother.dangling(),)

    def test_a_closed_subissue_with_no_run_left_open_is_not_dangling(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.closed(), SubIssueMother.pending())

        assert query.execute(_PARAMS).dangling == ()


class TestSelectingTheSliceNamedByTheCaller:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        repository.read_parent.side_effect = [
            ParentIssueMother.of_two_slices(),
            ParentIssueMother.with_exempt_controls(),
        ]
        repository.read_children.return_value = (SubIssueMother.pending(), SubIssueMother.of_another_repo())
        return repository

    @pytest.fixture
    def query(self, repository: Mock) -> SelectSlice:
        return SelectSlice(repository=repository)

    def test_naming_a_slice_picks_it_instead_of_the_first_one_that_is_runnable(self, query: SelectSlice) -> None:
        params = SelectSliceParams(repo=_REPO, issue=_ISSUE, slice_id=SubIssueMother.of_another_repo().slice_id)

        assert query.execute(params).subissue == SubIssueMother.of_another_repo()

    def test_a_slice_id_absent_from_every_child_raises_instead_of_falling_back_to_the_next_in_line(
        self, query: SelectSlice
    ) -> None:
        params = SelectSliceParams(repo=_REPO, issue=_ISSUE, slice_id="slice-99")

        with pytest.raises(NoSliceLeftError, match="slice-99"):
            query.execute(params)

    def test_a_slice_id_that_exists_but_is_closed_raises_instead_of_being_run_anyway(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.closed(), SubIssueMother.of_another_repo())
        params = SelectSliceParams(repo=_REPO, issue=_ISSUE, slice_id=SubIssueMother.closed().slice_id)

        with pytest.raises(NoSliceLeftError, match=SubIssueMother.closed().slice_id):
            query.execute(params)

    def test_a_slice_id_closed_by_github_while_its_own_run_was_open_still_closes_that_run_instead_of_only_raising(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        repository.read_children.return_value = (SubIssueMother.dangling(), SubIssueMother.of_another_repo())
        params = SelectSliceParams(repo=_REPO, issue=_ISSUE, slice_id=SubIssueMother.dangling().slice_id)

        with pytest.raises(NoSliceLeftError) as raised:
            query.execute(params)

        assert raised.value.dangling == (SubIssueMother.dangling(),)


class TestSelectSliceReopeningABlockedSliceOnAutoPick:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        repository.read_parent.side_effect = [
            ParentIssueMother.of_two_slices(),
            ParentIssueMother.with_exempt_controls(),
        ]
        return repository

    @pytest.fixture
    def query(self, repository: Mock) -> SelectSlice:
        return SelectSlice(repository=repository)

    def test_a_blocked_slice_with_a_retry_instruction_is_chosen_instead_of_raising(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        blocked = SubIssueMother.blocked(IssueLabel.BLOCKED_CI_RED, RunMother.blocked_on_red_ci())
        repository.read_children.return_value = (blocked,)
        repository.read_retry_instruction.return_value = RetryResponse(
            kind=RetryResponseKind.RETRY, instruction=_INSTRUCTION
        )

        result = query.execute(_PARAMS)

        assert result.subissue == blocked
        assert result.retry == RetryResponse(kind=RetryResponseKind.RETRY, instruction=_INSTRUCTION)

    def test_the_forum_is_asked_about_exactly_the_blocked_subissue(self, query: SelectSlice, repository: Mock) -> None:
        blocked = SubIssueMother.blocked(IssueLabel.BLOCKED_CI_RED, RunMother.blocked_on_red_ci())
        repository.read_children.return_value = (blocked,)
        repository.read_retry_instruction.return_value = RetryResponse(
            kind=RetryResponseKind.RETRY, instruction=_INSTRUCTION
        )

        query.execute(_PARAMS)

        repository.read_retry_instruction.assert_called_once_with(repo=_REPO, issue=blocked.number)

    def test_a_blocked_slice_with_no_retry_instruction_yet_still_raises_but_says_it_is_waiting_for_one(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        blocked = SubIssueMother.blocked(IssueLabel.BLOCKED_CI_RED, RunMother.blocked_on_red_ci())
        repository.read_children.return_value = (blocked,)
        repository.read_retry_instruction.return_value = RetryResponse(kind=RetryResponseKind.NOT_YET)

        with pytest.raises(NoSliceLeftError, match="retry instruction"):
            query.execute(_PARAMS)

    def test_a_runnable_slice_carries_no_retry_response_at_all(self, query: SelectSlice, repository: Mock) -> None:
        repository.read_children.return_value = (SubIssueMother.pending(),)

        assert query.execute(_PARAMS).retry is None


class TestSelectSliceReopeningTheSliceNamedByTheCaller:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        repository.read_parent.side_effect = [
            ParentIssueMother.of_two_slices(),
            ParentIssueMother.with_exempt_controls(),
        ]
        return repository

    @pytest.fixture
    def query(self, repository: Mock) -> SelectSlice:
        return SelectSlice(repository=repository)

    def test_naming_a_blocked_slice_with_a_retry_instruction_selects_it_instead_of_raising(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        blocked = SubIssueMother.blocked(IssueLabel.BLOCKED_VERIFY, RunMother.blocked_on_verify())
        repository.read_children.return_value = (blocked,)
        repository.read_retry_instruction.return_value = RetryResponse(
            kind=RetryResponseKind.RETRY, instruction=_INSTRUCTION
        )
        params = SelectSliceParams(repo=_REPO, issue=_ISSUE, slice_id=blocked.slice_id)

        result = query.execute(params)

        assert result.subissue == blocked
        assert result.retry == RetryResponse(kind=RetryResponseKind.RETRY, instruction=_INSTRUCTION)

    def test_naming_a_blocked_slice_with_no_retry_instruction_yet_raises_saying_it_is_waiting_for_one(
        self, query: SelectSlice, repository: Mock
    ) -> None:
        blocked = SubIssueMother.blocked(IssueLabel.BLOCKED_VERIFY, RunMother.blocked_on_verify())
        repository.read_children.return_value = (blocked,)
        repository.read_retry_instruction.return_value = RetryResponse(kind=RetryResponseKind.NOT_YET)
        params = SelectSliceParams(repo=_REPO, issue=_ISSUE, slice_id=blocked.slice_id)

        with pytest.raises(NoSliceLeftError, match="retry instruction"):
            query.execute(params)
