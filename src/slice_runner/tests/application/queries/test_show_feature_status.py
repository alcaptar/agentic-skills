from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.show_feature_status import ShowFeatureStatus, ShowFeatureStatusParams
from slice_runner.domain.branch_pull_request import BranchPullRequest
from slice_runner.domain.forum import Forum
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.slice_status import SliceStatus
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.run_mother import RunMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

_REPO = "alcaptar/agentic-skills"
_ISSUE = 38

_PARAMS = ShowFeatureStatusParams(repo=_REPO, issue=_ISSUE)


class TestShowFeatureStatus:
    @pytest.fixture
    def repository(self) -> Mock:
        repository: Mock = create_autospec(RunRepository, spec_set=True, instance=True)
        repository.read_parent.return_value = ParentIssueMother.of_two_slices()
        repository.read_children.return_value = (SubIssueMother.pending(), SubIssueMother.of_another_repo())
        return repository

    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.open_pull_requests.return_value = ()
        return forum

    @pytest.fixture
    def query(self, repository: Mock, forum: Mock) -> ShowFeatureStatus:
        return ShowFeatureStatus(repository=repository, forum=forum)

    def test_the_children_are_read_with_the_count_the_parent_declared(
        self, query: ShowFeatureStatus, repository: Mock
    ) -> None:
        query.execute(_PARAMS)

        repository.read_children.assert_called_once_with(repo=_REPO, parent=_ISSUE, expected=2)

    def test_one_status_comes_back_per_child_in_the_order_they_were_read(self, query: ShowFeatureStatus) -> None:
        statuses = query.execute(_PARAMS)

        assert statuses == (
            SliceStatus(sub_issue=SubIssueMother.pending(), pull_request=None),
            SliceStatus(sub_issue=SubIssueMother.of_another_repo(), pull_request=None),
        )

    def test_the_pull_requests_are_asked_for_with_every_branch_of_the_children_at_once(
        self, query: ShowFeatureStatus, forum: Mock
    ) -> None:
        query.execute(_PARAMS)

        forum.open_pull_requests.assert_called_once_with(
            repo=_REPO,
            branches=(SubIssueMother.pending().branch, SubIssueMother.of_another_repo().branch),
        )

    def test_a_child_whose_branch_carries_an_open_pull_request_gets_its_number(
        self, query: ShowFeatureStatus, forum: Mock
    ) -> None:
        forum.open_pull_requests.return_value = (BranchPullRequest(branch=SubIssueMother.pending().branch, number=47),)

        statuses = query.execute(_PARAMS)

        assert statuses[0].pull_request == 47
        assert statuses[1].pull_request is None

    @pytest.mark.parametrize("child_count", [2, 10])
    def test_the_number_of_calls_to_the_forum_does_not_grow_with_the_number_of_slices(
        self, query: ShowFeatureStatus, repository: Mock, forum: Mock, child_count: int
    ) -> None:
        repository.read_children.return_value = tuple(
            SubIssueMother.carrying(IssueLabel.PENDING) for _ in range(child_count)
        )

        query.execute(_PARAMS)

        assert forum.open_pull_requests.call_count == 1

    def test_no_write_method_of_the_repository_is_ever_called(self, query: ShowFeatureStatus, repository: Mock) -> None:
        query.execute(_PARAMS)

        assert {name for name, _args, _kwargs in repository.method_calls} <= {"read_parent", "read_children"}

    def test_a_blocked_or_an_aborted_slice_passes_through_instead_of_raising(
        self, query: ShowFeatureStatus, repository: Mock
    ) -> None:
        repository.read_children.return_value = (
            SubIssueMother.blocked(IssueLabel.BLOCKED_CI_RED, RunMother.blocked_on_red_ci()),
            SubIssueMother.blocked(IssueLabel.ABORTED_BUDGET, RunMother.aborted_for_budget(RunMother.judging().spend)),
        )

        statuses = query.execute(_PARAMS)

        assert len(statuses) == 2
