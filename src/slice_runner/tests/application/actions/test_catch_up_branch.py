from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.catch_up_branch import CatchUpBranch, CatchUpBranchParams
from slice_runner.domain.branch_catch_up import BranchCatchUp
from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.branches import Branches
from slice_runner.domain.conflict_block_cause import ConflictBlockCause
from slice_runner.domain.conflict_resolver import ConflictResolver
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.resolution import Resolution
from slice_runner.domain.source import Source, SourceKind
from slice_runner.domain.workspace import Workspace
from slice_runner.infrastructure.git_branches import GitBranches
from slice_runner.infrastructure.git_workspace import GitWorkspace
from slice_runner.tests.git_repo import Git
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.merge_conflict_mother import MergeConflictMother
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from slice_runner.domain.merge_conflict import MergeConflict

_SOURCES = (Source(kind=SourceKind.DOC, path="CLAUDE.md"),)


class TestCatchUpBranch:
    @pytest.fixture
    def branches(self) -> Mock:
        doubled: Mock = create_autospec(Branches, spec_set=True, instance=True)
        doubled.catch_up.return_value = BranchCatchUp(outcome=BranchCatchUpOutcome.CAUGHT_UP)
        doubled.paths_touched_since_the_merge_attempt.return_value = ("shared.txt",)
        doubled.has_leftover_conflict_markers.return_value = False
        return doubled

    @pytest.fixture
    def workspace(self) -> Mock:
        doubled: Mock = create_autospec(Workspace, spec_set=True, instance=True)
        return doubled

    @pytest.fixture
    def resolver(self) -> Mock:
        doubled: Mock = create_autospec(ConflictResolver, spec_set=True, instance=True)
        doubled.resolve.return_value = Resolution(spend=HarnessSpendMother.of_the_catch_up_call())
        return doubled

    @pytest.fixture
    def action(self, branches: Mock, workspace: Mock, resolver: Mock) -> CatchUpBranch:
        return CatchUpBranch(branches=branches, workspace=workspace, resolver=resolver)

    @staticmethod
    def _params() -> CatchUpBranchParams:
        return CatchUpBranchParams(
            repo=MergeConflictMother.REPO,
            issue=MergeConflictMother.ISSUE,
            slice_id=MergeConflictMother.SLICE_ID,
            worktree=MergeConflictMother.WORKTREE,
            branch=MergeConflictMother.BRANCH,
            base=MergeConflictMother.BASE,
            sources=_SOURCES,
        )

    @staticmethod
    def _conflicting(*, branches: Mock, conflicted_paths: tuple[str, ...] = ("shared.txt",)) -> None:
        branches.catch_up.return_value = BranchCatchUp(
            outcome=BranchCatchUpOutcome.CONFLICTING, conflicted_paths=conflicted_paths
        )


class TestTheResolverIsOnlyCalledWhenGitLeavesAConflict(TestCatchUpBranch):
    def test_a_clean_catch_up_never_calls_the_resolver(self, action: CatchUpBranch, resolver: Mock) -> None:
        action.execute(self._params())

        assert resolver.resolve.call_count == 0

    def test_a_clean_catch_up_projects_to_done_without_a_spend(self, action: CatchUpBranch) -> None:
        result = action.execute(self._params())

        assert (result.outcome, result.spend) == (Outcome.DONE, None)

    def test_it_asks_the_port_to_catch_up_the_declared_branch_against_its_base(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        params = self._params()

        action.execute(params)

        branches.catch_up.assert_called_once_with(worktree=params.worktree, name=params.branch, base=params.base)

    def test_a_conflicting_catch_up_calls_the_resolver_exactly_once(
        self, action: CatchUpBranch, branches: Mock, resolver: Mock
    ) -> None:
        self._conflicting(branches=branches)

        action.execute(self._params())

        assert resolver.resolve.call_count == 1

    def test_the_resolver_receives_the_conflicted_paths_and_the_sources_of_the_parent(
        self, action: CatchUpBranch, branches: Mock, resolver: Mock
    ) -> None:
        self._conflicting(branches=branches)

        action.execute(self._params())

        assert resolver.resolve.call_args.args[0] == MergeConflictMother.of_one_conflicted_file()


class TestAFileOutsideTheConflictIsRejected(TestCatchUpBranch):
    def test_touching_a_clean_file_is_rejected_instead_of_concluding_the_merge(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        self._conflicting(branches=branches)
        branches.paths_touched_since_the_merge_attempt.return_value = ("shared.txt", "clean.txt")

        result = action.execute(self._params())

        assert result.outcome is Outcome.HYGIENE_REJECTED

    def test_touching_a_clean_file_aborts_the_merge_instead_of_concluding_it(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        self._conflicting(branches=branches)
        branches.paths_touched_since_the_merge_attempt.return_value = ("shared.txt", "clean.txt")

        action.execute(self._params())

        assert branches.abort_merge.call_count == 1
        assert branches.conclude_merge.call_count == 0

    def test_touching_a_clean_file_still_carries_what_the_resolver_spent(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        self._conflicting(branches=branches)
        branches.paths_touched_since_the_merge_attempt.return_value = ("shared.txt", "clean.txt")

        result = action.execute(self._params())

        assert result.spend == HarnessSpendMother.of_the_catch_up_call()

    def test_touching_a_clean_file_names_the_tree_as_still_conflicted_instead_of_leaving_the_conductor_to_guess(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        self._conflicting(branches=branches)
        branches.paths_touched_since_the_merge_attempt.return_value = ("shared.txt", "clean.txt")

        result = action.execute(self._params())

        assert result.conflict_block_cause is ConflictBlockCause.TREE_STILL_CONFLICTED


class TestATreeStillConflictedAfterTheResolverIsRejected(TestCatchUpBranch):
    def test_leftover_conflict_markers_are_rejected_instead_of_concluding_the_merge(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        self._conflicting(branches=branches)
        branches.has_leftover_conflict_markers.return_value = True

        result = action.execute(self._params())

        assert result.outcome is Outcome.FAILED

    def test_leftover_conflict_markers_abort_the_merge_instead_of_concluding_it(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        self._conflicting(branches=branches)
        branches.has_leftover_conflict_markers.return_value = True

        action.execute(self._params())

        assert branches.abort_merge.call_count == 1
        assert branches.conclude_merge.call_count == 0

    def test_leftover_conflict_markers_name_the_tree_as_still_conflicted_instead_of_leaving_the_conductor_to_guess(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        self._conflicting(branches=branches)
        branches.has_leftover_conflict_markers.return_value = True

        result = action.execute(self._params())

        assert result.conflict_block_cause is ConflictBlockCause.TREE_STILL_CONFLICTED


class TestAConflictTheResolverFixedCleanly(TestCatchUpBranch):
    def test_it_concludes_the_merge_by_staging_exactly_the_conflicted_paths(
        self, action: CatchUpBranch, branches: Mock, workspace: Mock
    ) -> None:
        self._conflicting(branches=branches, conflicted_paths=("shared.txt",))

        action.execute(self._params())

        workspace.stage.assert_called_once_with(worktree=MergeConflictMother.WORKTREE, paths=("shared.txt",))
        assert branches.conclude_merge.call_count == 1
        assert branches.abort_merge.call_count == 0

    def test_it_reports_the_resolution_as_done_and_as_having_resolved_a_conflict(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        self._conflicting(branches=branches)

        result = action.execute(self._params())

        assert (result.outcome, result.resolved_a_conflict) == (Outcome.DONE, True)

    def test_it_reports_no_conflict_block_cause_once_the_tree_is_resolved(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        self._conflicting(branches=branches)

        result = action.execute(self._params())

        assert result.conflict_block_cause is None

    def test_it_carries_what_the_resolver_spent(self, action: CatchUpBranch, branches: Mock) -> None:
        self._conflicting(branches=branches)

        result = action.execute(self._params())

        assert result.spend == HarnessSpendMother.of_the_catch_up_call()


class FakeResolver(ConflictResolver):
    def __init__(self, *, writes: dict[str, str]) -> None:
        self._writes = writes
        self.conflicts: list[MergeConflict] = []

    def resolve(self, conflict: MergeConflict) -> Resolution:
        self.conflicts.append(conflict)
        for path, content in self._writes.items():
            (Path(conflict.worktree) / path).write_text(content)

        return Resolution(spend=HarnessSpendMother.of_the_catch_up_call())


@pytest.mark.integration
class TestCatchUpBranchAgainstARealConflict:
    _SLICE_BRANCH = "slice/04-el-conflicto-de-contenido-lo-resuelve-un-agente"

    @classmethod
    def _repo_with_a_conflict_in_progress(
        cls, tmp_path: Path, *, extra_clean_file: bool = False, base_also_edits_the_clean_file: bool = False
    ) -> Path:
        remote = tmp_path / "remote.git"
        Git.run(tmp_path, "init", "--bare", str(remote))
        repo = Git.init_repo(tmp_path / "repo")
        (repo / "shared.txt").write_text("base\n")
        if extra_clean_file or base_also_edits_the_clean_file:
            (repo / "clean.txt").write_text("clean\n")
        Git.run(repo, "add", "-A")
        Git.run(repo, "commit", "-m", "base")
        Git.run(repo, "remote", "add", "origin", str(remote))
        Git.run(repo, "push", "-u", "origin", Git.BASE_BRANCH)
        Git.run(repo, "switch", "-c", cls._SLICE_BRANCH, f"origin/{Git.BASE_BRANCH}")
        (repo / "shared.txt").write_text("from the branch\n")
        Git.run(repo, "commit", "-am", "branch edit")
        Git.run(repo, "push", "-u", "origin", cls._SLICE_BRANCH)
        Git.run(repo, "switch", Git.BASE_BRANCH)
        (repo / "shared.txt").write_text("from the base\n")
        if base_also_edits_the_clean_file:
            (repo / "clean.txt").write_text("edited cleanly by the base\n")
        Git.run(repo, "commit", "-am", "base edit")
        Git.run(repo, "push")
        Git.run(repo, "switch", cls._SLICE_BRANCH)
        GitBranches(process=Real.process()).catch_up(worktree=str(repo), name=cls._SLICE_BRANCH, base=Git.BASE_BRANCH)

        return repo

    def _action(self, *, resolver: ConflictResolver) -> CatchUpBranch:
        process = Real.process()

        return CatchUpBranch(
            branches=GitBranches(process=process), workspace=GitWorkspace(process=process), resolver=resolver
        )

    @staticmethod
    def _params(*, worktree: Path) -> CatchUpBranchParams:
        return CatchUpBranchParams(
            repo=MergeConflictMother.REPO,
            issue=MergeConflictMother.ISSUE,
            slice_id=MergeConflictMother.SLICE_ID,
            worktree=str(worktree),
            branch=TestCatchUpBranchAgainstARealConflict._SLICE_BRANCH,
            base=Git.BASE_BRANCH,
            sources=(),
        )

    def test_a_resolution_that_removes_every_marker_concludes_the_merge(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_conflict_in_progress(tmp_path)
        action = self._action(resolver=FakeResolver(writes={"shared.txt": "resolved\n"}))

        result = action.execute(self._params(worktree=repo))

        assert (result.outcome, result.resolved_a_conflict) == (Outcome.DONE, True)
        assert not (repo / ".git" / "MERGE_HEAD").exists()
        assert (repo / "shared.txt").read_text() == "resolved\n"

    def test_a_resolution_that_leaves_markers_behind_aborts_the_merge(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_conflict_in_progress(tmp_path)
        action = self._action(resolver=FakeResolver(writes={}))

        result = action.execute(self._params(worktree=repo))

        assert result.outcome is Outcome.FAILED
        assert not (repo / ".git" / "MERGE_HEAD").exists()
        assert (repo / "shared.txt").read_text() == "from the branch\n"

    def test_a_resolution_that_touches_a_file_outside_the_conflict_aborts_the_merge(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_conflict_in_progress(tmp_path, extra_clean_file=True)
        action = self._action(resolver=FakeResolver(writes={"shared.txt": "resolved\n", "clean.txt": "touched\n"}))

        result = action.execute(self._params(worktree=repo))

        assert result.outcome is Outcome.HYGIENE_REJECTED
        assert not (repo / ".git" / "MERGE_HEAD").exists()

    def test_a_valid_resolution_concludes_the_merge_even_when_the_base_also_edited_another_file_cleanly(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo_with_a_conflict_in_progress(tmp_path, base_also_edits_the_clean_file=True)
        action = self._action(resolver=FakeResolver(writes={"shared.txt": "resolved\n"}))

        result = action.execute(self._params(worktree=repo))

        assert (result.outcome, result.resolved_a_conflict) == (Outcome.DONE, True)
        assert not (repo / ".git" / "MERGE_HEAD").exists()
        assert (repo / "clean.txt").read_text() == "edited cleanly by the base\n"
