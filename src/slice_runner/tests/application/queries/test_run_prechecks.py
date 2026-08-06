from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.run_prechecks import RunPrechecks, RunPrechecksParams
from slice_runner.domain.branches import Branches
from slice_runner.domain.forum import Forum
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue

_REPO = "alcaptar/agentic-skills"
_WORKTREE = "/repos/agentic-skills"
_BRANCH = "slice/05-prechecks-deterministas"


class TestRunPrechecks:
    @pytest.fixture
    def branches(self) -> Mock:
        branches: Mock = create_autospec(Branches, spec_set=True, instance=True)
        branches.exists.return_value = False
        return branches

    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.open_pull_request.return_value = None
        return forum

    @pytest.fixture
    def query(self, branches: Mock, forum: Mock) -> RunPrechecks:
        return RunPrechecks(branches=branches, forum=forum)

    @staticmethod
    def _params(*, subissue: SubIssue, parent: ParentIssue) -> RunPrechecksParams:
        return RunPrechecksParams(repo=_REPO, worktree=_WORKTREE, branch=_BRANCH, subissue=subissue, parent=parent)

    def test_a_closed_subissue_wins_even_with_everything_else_clear(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.closed(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params) is PrecheckOutcome.SUBISSUE_ALREADY_CLOSED

    def test_a_slice_of_another_repo_is_refused_before_anything_measured_against_this_one_is_believed(
        self, query: RunPrechecks, branches: Mock, forum: Mock
    ) -> None:
        branches.exists.return_value = True
        forum.open_pull_request.return_value = 47
        params = self._params(
            subissue=SubIssueMother.of_another_repo(), parent=ParentIssueMother.with_sources_and_controls()
        )

        assert query.execute(params) is PrecheckOutcome.SLICE_IN_ANOTHER_REPO

    def test_an_open_pull_request_wins_over_an_existing_branch_because_it_is_the_more_informative_reason(
        self, query: RunPrechecks, branches: Mock, forum: Mock
    ) -> None:
        branches.exists.return_value = True
        forum.open_pull_request.return_value = 47
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params) is PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN

    def test_an_existing_branch_with_no_pull_request_is_its_own_reason(
        self, query: RunPrechecks, branches: Mock
    ) -> None:
        branches.exists.return_value = True
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params) is PrecheckOutcome.BRANCH_ALREADY_EXISTS

    def test_a_parent_with_no_sources_is_missing_sources(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.without_sources())

        assert query.execute(params) is PrecheckOutcome.MISSING_SOURCES

    def test_a_parent_with_sources_and_no_controls_is_missing_controls(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.without_controls())

        assert query.execute(params) is PrecheckOutcome.MISSING_CONTROLS

    def test_everything_in_its_place_is_clear(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params) is PrecheckOutcome.CLEAR

    def test_a_declared_exemption_is_clear_even_though_it_carries_no_command_to_run(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_exempt_controls())

        assert query.execute(params) is PrecheckOutcome.CLEAR

    def test_the_ports_are_asked_about_the_worktree_the_branch_and_the_repo_the_params_carried(
        self, query: RunPrechecks, branches: Mock, forum: Mock
    ) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        query.execute(params)

        branches.exists.assert_called_once_with(worktree=_WORKTREE, name=_BRANCH)
        forum.open_pull_request.assert_called_once_with(repo=_REPO, branch=_BRANCH)
