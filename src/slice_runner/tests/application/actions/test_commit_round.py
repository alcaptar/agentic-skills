from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.commit_round import CommitRound, CommitRoundParams
from slice_runner.domain.exceptions import BranchMismatchError, ProtectedBranchError
from slice_runner.domain.protected_branch import ProtectedBranch
from slice_runner.domain.workspace import Workspace

_WORKTREE = "/repos/agentic-skills"
_BRANCH = "slice/14-una-correccion-va-en-su-propio-commit"
_MESSAGE = "feat(una-correccion): el commit de la vuelta 2\n\nCo-Authored-By: Claude <noreply@anthropic.com>"


class TestCommitRound:
    @pytest.fixture
    def workspace(self) -> Mock:
        workspace: Mock = create_autospec(Workspace, spec_set=True, instance=True)
        workspace.current_branch.return_value = _BRANCH
        workspace.staged.return_value = ("src/mod.py",)
        return workspace

    @pytest.fixture
    def action(self, workspace: Mock) -> CommitRound:
        return CommitRound(workspace=workspace)

    @staticmethod
    def _params() -> CommitRoundParams:
        return CommitRoundParams(worktree=_WORKTREE, branch=_BRANCH, message=_MESSAGE)

    def test_a_round_with_something_staged_is_committed_with_the_message_it_was_given(
        self, action: CommitRound, workspace: Mock
    ) -> None:
        action.execute(self._params())

        workspace.commit.assert_called_once_with(worktree=_WORKTREE, message=_MESSAGE)

    def test_a_round_with_nothing_staged_leaves_no_commit(self, action: CommitRound, workspace: Mock) -> None:
        workspace.staged.return_value = ()

        action.execute(self._params())

        workspace.commit.assert_not_called()

    @pytest.mark.parametrize("protected", list(ProtectedBranch))
    def test_a_protected_branch_stops_the_round_before_anything_is_committed(
        self, action: CommitRound, workspace: Mock, protected: ProtectedBranch
    ) -> None:
        workspace.current_branch.return_value = str(protected)

        with pytest.raises(ProtectedBranchError, match=str(protected)):
            action.execute(self._params())

        workspace.commit.assert_not_called()

    def test_standing_on_a_branch_that_is_not_the_one_the_slice_declared_stops_the_round(
        self, action: CommitRound, workspace: Mock
    ) -> None:
        workspace.current_branch.return_value = "slice/07-otra-slice"

        with pytest.raises(BranchMismatchError, match="slice/07-otra-slice"):
            action.execute(self._params())

        workspace.commit.assert_not_called()
