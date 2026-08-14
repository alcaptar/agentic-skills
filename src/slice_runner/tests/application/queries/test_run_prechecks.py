from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.queries.run_prechecks import RunPrechecks, RunPrechecksParams
from slice_runner.domain.branches import Branches
from slice_runner.domain.exceptions import SourcesBudgetExceededError, UnreadableSourceError, UnresolvableBaseError
from slice_runner.domain.forum import Forum
from slice_runner.domain.precheck_outcome import PrecheckOutcome
from slice_runner.domain.source_reader import SourceReader
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue

_REPO = "alcaptar/agentic-skills"
_WORKTREE = "/repos/agentic-skills"
_BRANCH = "slice/05-prechecks-deterministas"
_BASE = "master"


class TestRunPrechecks:
    @pytest.fixture
    def branches(self) -> Mock:
        branches: Mock = create_autospec(Branches, spec_set=True, instance=True)
        branches.exists.return_value = False
        branches.commits_behind_remote.return_value = 0
        return branches

    @pytest.fixture
    def forum(self) -> Mock:
        forum: Mock = create_autospec(Forum, spec_set=True, instance=True)
        forum.open_pull_request.return_value = None
        return forum

    @pytest.fixture
    def sources(self) -> Mock:
        sources: Mock = create_autospec(SourceReader, spec_set=True, instance=True)
        sources.read_all.return_value = ()
        return sources

    @pytest.fixture
    def query(self, branches: Mock, forum: Mock, sources: Mock) -> RunPrechecks:
        return RunPrechecks(branches=branches, forum=forum, sources=sources)

    @staticmethod
    def _params(*, subissue: SubIssue, parent: ParentIssue) -> RunPrechecksParams:
        return RunPrechecksParams(
            repo=_REPO, worktree=_WORKTREE, branch=_BRANCH, base=_BASE, subissue=subissue, parent=parent
        )

    def test_a_closed_subissue_wins_even_with_everything_else_clear(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.closed(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params).outcome is PrecheckOutcome.SUBISSUE_ALREADY_CLOSED

    def test_a_slice_of_another_repo_is_refused_before_anything_measured_against_this_one_is_believed(
        self, query: RunPrechecks, branches: Mock, forum: Mock
    ) -> None:
        branches.exists.return_value = True
        forum.open_pull_request.return_value = 47
        params = self._params(
            subissue=SubIssueMother.of_another_repo(), parent=ParentIssueMother.with_sources_and_controls()
        )

        assert query.execute(params).outcome is PrecheckOutcome.SLICE_IN_ANOTHER_REPO

    def test_an_open_pull_request_wins_over_an_existing_branch_because_it_is_the_more_informative_reason(
        self, query: RunPrechecks, branches: Mock, forum: Mock
    ) -> None:
        branches.exists.return_value = True
        forum.open_pull_request.return_value = 47
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params).outcome is PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN

    def test_an_existing_branch_with_no_pull_request_is_its_own_reason(
        self, query: RunPrechecks, branches: Mock
    ) -> None:
        branches.exists.return_value = True
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        result = query.execute(params)

        assert result.outcome is PrecheckOutcome.BRANCH_ALREADY_EXISTS
        assert result.reason is None

    def test_a_base_that_does_not_resolve_against_its_remote_is_its_own_reason(
        self, query: RunPrechecks, branches: Mock
    ) -> None:
        branches.commits_behind_remote.side_effect = UnresolvableBaseError(f"{_BASE} does not resolve")
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params).outcome is PrecheckOutcome.BASE_NOT_ON_REMOTE

    def test_a_base_that_does_not_resolve_wins_over_an_existing_branch_because_nothing_can_be_trusted_without_it(
        self, query: RunPrechecks, branches: Mock
    ) -> None:
        branches.exists.return_value = True
        branches.commits_behind_remote.side_effect = UnresolvableBaseError(f"{_BASE} does not resolve")
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params).outcome is PrecheckOutcome.BASE_NOT_ON_REMOTE

    def test_the_base_the_params_carried_is_what_gets_asked_about(self, query: RunPrechecks, branches: Mock) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        query.execute(params)

        branches.commits_behind_remote.assert_called_once_with(worktree=_WORKTREE, base=_BASE)

    def test_a_parent_with_no_sources_is_missing_sources(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.without_sources())

        assert query.execute(params).outcome is PrecheckOutcome.MISSING_SOURCES

    def test_a_parent_with_sources_and_no_controls_is_missing_controls(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.without_controls())

        assert query.execute(params).outcome is PrecheckOutcome.MISSING_CONTROLS

    def test_a_declared_source_that_cannot_be_read_is_its_own_reason(self, query: RunPrechecks, sources: Mock) -> None:
        sources.read_all.side_effect = UnreadableSourceError("CLAUDE.md does not exist under the worktree")
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        result = query.execute(params)

        assert result.outcome is PrecheckOutcome.UNREADABLE_SOURCE
        assert result.reason == "CLAUDE.md does not exist under the worktree"

    def test_an_unreadable_source_wins_over_missing_controls_because_it_is_checked_first(
        self, query: RunPrechecks, sources: Mock
    ) -> None:
        sources.read_all.side_effect = UnreadableSourceError("CLAUDE.md does not exist under the worktree")
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.without_controls())

        assert query.execute(params).outcome is PrecheckOutcome.UNREADABLE_SOURCE

    def test_declared_sources_over_the_size_budget_are_their_own_reason(
        self, query: RunPrechecks, sources: Mock
    ) -> None:
        sources.read_all.side_effect = SourcesBudgetExceededError("the declared sources are over budget")
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        result = query.execute(params)

        assert result.outcome is PrecheckOutcome.SOURCES_OVER_BUDGET
        assert result.reason == "the declared sources are over budget"

    def test_sources_over_budget_wins_over_missing_controls_because_it_is_checked_first(
        self, query: RunPrechecks, sources: Mock
    ) -> None:
        sources.read_all.side_effect = SourcesBudgetExceededError("the declared sources are over budget")
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.without_controls())

        assert query.execute(params).outcome is PrecheckOutcome.SOURCES_OVER_BUDGET

    def test_an_existing_branch_wins_over_sources_that_are_over_budget_because_it_is_the_more_informative_reason(
        self, query: RunPrechecks, branches: Mock, sources: Mock
    ) -> None:
        branches.exists.return_value = True
        sources.read_all.side_effect = SourcesBudgetExceededError("the declared sources are over budget")
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        result = query.execute(params)

        assert result.outcome is PrecheckOutcome.BRANCH_ALREADY_EXISTS
        assert result.reason is None

    def test_an_open_pull_request_wins_over_sources_that_are_over_budget_because_it_is_the_more_informative_reason(
        self, query: RunPrechecks, forum: Mock, sources: Mock
    ) -> None:
        forum.open_pull_request.return_value = 47
        sources.read_all.side_effect = SourcesBudgetExceededError("the declared sources are over budget")
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        result = query.execute(params)

        assert result.outcome is PrecheckOutcome.PULL_REQUEST_ALREADY_OPEN
        assert result.reason is None

    def test_everything_in_its_place_is_clear(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_sources_and_controls())

        assert query.execute(params).outcome is PrecheckOutcome.CLEAR

    def test_a_declared_exemption_is_clear_even_though_it_carries_no_command_to_run(self, query: RunPrechecks) -> None:
        params = self._params(subissue=SubIssueMother.pending(), parent=ParentIssueMother.with_exempt_controls())

        assert query.execute(params).outcome is PrecheckOutcome.CLEAR

    def test_the_ports_are_asked_about_the_worktree_the_branch_and_the_repo_the_params_carried(
        self, query: RunPrechecks, branches: Mock, forum: Mock, sources: Mock
    ) -> None:
        parent = ParentIssueMother.with_sources_and_controls()
        params = self._params(subissue=SubIssueMother.pending(), parent=parent)

        query.execute(params)

        branches.exists.assert_called_once_with(worktree=_WORKTREE, name=_BRANCH)
        forum.open_pull_request.assert_called_once_with(repo=_REPO, branch=_BRANCH)
        sources.read_all.assert_called_once_with(worktree=_WORKTREE, sources=parent.sources)
