from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.catch_up_branch import CatchUpBranch, CatchUpBranchParams
from slice_runner.domain.branches import Branches
from slice_runner.domain.conflict_resolution import ConflictResolution
from slice_runner.domain.conflict_resolver import ConflictResolver
from slice_runner.domain.exceptions import InvalidResolutionReportError
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.source import Source, SourceKind
from slice_runner.domain.workspace import Workspace
from slice_runner.infrastructure.git_branches import GitBranches
from slice_runner.infrastructure.git_workspace import GitWorkspace
from slice_runner.tests.git_repo import Git
from slice_runner.tests.mothers.branch_catch_up_mother import BranchCatchUpMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from slice_runner.domain.merge_conflict import MergeConflict

_REPO = "alcaptar/agentic-skills"
_ISSUE = 38
_SLICE_ID = "slice-07"
_WORKTREE = "/repos/agentic-skills"
_BRANCH = "slice/07-el-conflicto-de-contenido-lo-resuelve-un-agente"
_BASE = "master"
_SOURCES = (Source(kind=SourceKind.DOC, path="CLAUDE.md"),)
_CLEAN_FILE = "README.md"


class TestCatchUpBranch:
    @pytest.fixture
    def branches(self) -> Mock:
        doubled: Mock = create_autospec(Branches, spec_set=True, instance=True)
        doubled.catch_up.return_value = BranchCatchUpMother.caught_up()
        doubled.changed_paths.return_value = ()
        return doubled

    @pytest.fixture
    def workspace(self) -> Mock:
        doubled: Mock = create_autospec(Workspace, spec_set=True, instance=True)
        return doubled

    @pytest.fixture
    def resolver(self) -> Mock:
        doubled: Mock = create_autospec(ConflictResolver, spec_set=True, instance=True)
        doubled.resolve.return_value = ConflictResolution(spend=HarnessSpendMother.of_the_implementer_call())
        return doubled

    @pytest.fixture
    def action(self, branches: Mock, workspace: Mock, resolver: Mock) -> CatchUpBranch:
        return CatchUpBranch(branches=branches, workspace=workspace, resolver=resolver)

    @staticmethod
    def _params() -> CatchUpBranchParams:
        return CatchUpBranchParams(
            repo=_REPO,
            issue=_ISSUE,
            slice_id=_SLICE_ID,
            worktree=_WORKTREE,
            branch=_BRANCH,
            base=_BASE,
            sources=_SOURCES,
        )

    def test_it_asks_the_port_to_catch_up_the_declared_branch_against_its_base(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        action.execute(self._params())

        branches.catch_up.assert_called_once_with(worktree=_WORKTREE, name=_BRANCH, base=_BASE)

    def test_a_clean_catch_up_never_calls_the_resolver(self, action: CatchUpBranch, resolver: Mock) -> None:
        action.execute(self._params())

        assert resolver.resolve.call_count == 0

    def test_a_clean_catch_up_projects_to_done_with_no_spend_to_report(self, action: CatchUpBranch) -> None:
        result = action.execute(self._params())

        assert (result.outcome, result.spend) == (Outcome.DONE, None)

    def test_a_conflicting_catch_up_calls_the_resolver_exactly_once(
        self, action: CatchUpBranch, branches: Mock, resolver: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        action.execute(self._params())

        assert resolver.resolve.call_count == 1

    def test_the_resolver_receives_the_conflicting_paths_and_the_sources_of_the_slice(
        self, action: CatchUpBranch, branches: Mock, resolver: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        action.execute(self._params())

        conflict: MergeConflict = resolver.resolve.call_args.args[0]
        assert (conflict.conflicting_paths, conflict.sources) == (BranchCatchUpMother.CONFLICTING_PATHS, _SOURCES)
        assert (conflict.repo, conflict.issue, conflict.slice_id) == (_REPO, _ISSUE, _SLICE_ID)
        assert (conflict.worktree, conflict.branch, conflict.base) == (_WORKTREE, _BRANCH, _BASE)

    def test_a_resolved_conflict_stages_the_conflicting_paths_before_concluding(
        self, action: CatchUpBranch, branches: Mock, workspace: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        action.execute(self._params())

        workspace.stage.assert_called_once_with(worktree=_WORKTREE, paths=BranchCatchUpMother.CONFLICTING_PATHS)
        branches.conclude_merge.assert_called_once_with(worktree=_WORKTREE)
        assert branches.abort_merge.call_count == 0

    def test_a_resolved_conflict_projects_to_done_carrying_what_the_resolver_spent(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()

        result = action.execute(self._params())

        assert (result.outcome, result.spend) == (Outcome.DONE, HarnessSpendMother.of_the_implementer_call())

    def test_a_resolver_that_touches_a_file_outside_the_conflict_gets_its_round_rejected(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()
        branches.changed_paths.side_effect = [
            BranchCatchUpMother.CONFLICTING_PATHS,
            (*BranchCatchUpMother.CONFLICTING_PATHS, _CLEAN_FILE),
        ]

        result = action.execute(self._params())

        assert result.outcome is Outcome.HYGIENE_REJECTED

    def test_a_resolver_that_touches_a_file_outside_the_conflict_never_gets_the_merge_concluded(
        self, action: CatchUpBranch, branches: Mock, workspace: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()
        branches.changed_paths.side_effect = [
            BranchCatchUpMother.CONFLICTING_PATHS,
            (*BranchCatchUpMother.CONFLICTING_PATHS, _CLEAN_FILE),
        ]

        action.execute(self._params())

        assert branches.conclude_merge.call_count == 0
        assert workspace.stage.call_count == 0

    def test_a_resolver_that_touches_a_file_outside_the_conflict_has_its_merge_aborted(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()
        branches.changed_paths.side_effect = [
            BranchCatchUpMother.CONFLICTING_PATHS,
            (*BranchCatchUpMother.CONFLICTING_PATHS, _CLEAN_FILE),
        ]

        action.execute(self._params())

        branches.abort_merge.assert_called_once_with(worktree=_WORKTREE)

    def test_a_file_git_already_resolved_on_its_own_does_not_count_as_an_offence(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        already_resolved = (*BranchCatchUpMother.CONFLICTING_PATHS, _CLEAN_FILE)
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_with_a_file_already_dirty_before_the_merge(
            dirty=()
        )
        branches.changed_paths.side_effect = [already_resolved, already_resolved]

        result = action.execute(self._params())

        assert result.outcome is Outcome.DONE

    def test_a_file_already_dirty_before_the_merge_still_counts_as_an_offence_even_untouched_by_the_resolver(
        self, action: CatchUpBranch, branches: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_with_a_file_already_dirty_before_the_merge(
            dirty=(_CLEAN_FILE,)
        )
        staged_throughout = (*BranchCatchUpMother.CONFLICTING_PATHS, _CLEAN_FILE)
        branches.changed_paths.side_effect = [staged_throughout, staged_throughout]

        result = action.execute(self._params())

        assert result.outcome is Outcome.HYGIENE_REJECTED

    def test_a_dead_resolver_call_aborts_the_merge_instead_of_leaving_it_half_resolved(
        self, action: CatchUpBranch, branches: Mock, resolver: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()
        resolver.resolve.side_effect = InvalidResolutionReportError("the resolver never emitted a report")

        result = action.execute(self._params())

        branches.abort_merge.assert_called_once_with(worktree=_WORKTREE)
        assert result.outcome is Outcome.DISCARDED

    def test_a_dead_resolver_call_still_carries_what_it_spent_so_the_budget_still_sees_it(
        self, action: CatchUpBranch, branches: Mock, resolver: Mock
    ) -> None:
        branches.catch_up.return_value = BranchCatchUpMother.conflicting_on_a_shared_file()
        rejection = InvalidResolutionReportError("the resolver never emitted a report")
        rejection.spend = HarnessSpendMother.of_a_call_that_cost_nothing()
        resolver.resolve.side_effect = rejection

        result = action.execute(self._params())

        assert result.spend == HarnessSpendMother.of_a_call_that_cost_nothing()


class _EditingResolver(ConflictResolver):
    def __init__(self, *, edits: dict[str, str]) -> None:
        self._edits = edits
        self.calls = 0

    def resolve(self, conflict: MergeConflict) -> ConflictResolution:
        self.calls += 1
        for path, content in self._edits.items():
            (Path(conflict.worktree) / path).write_text(content)

        return ConflictResolution(spend=HarnessSpendMother.of_the_implementer_call())


@pytest.mark.integration
class TestCatchUpBranchAgainstARealGitRepository:
    _SLICE_BRANCH = "slice/22-la-rama-se-pone-al-dia"

    @staticmethod
    def _repo_with_a_conflicting_edit_pushed_from_elsewhere(tmp_path: Path) -> Path:
        repo, _ = Git.repo_with_a_conflicting_edit_pushed_from_elsewhere(
            tmp_path,
            branch=TestCatchUpBranchAgainstARealGitRepository._SLICE_BRANCH,
            extra_files={"clean.txt": "base\n"},
        )
        (repo / "shared.txt").write_text("from the worktree\n")
        Git.run(repo, "commit", "-am", "edited locally")

        return repo

    @staticmethod
    def _action(*, resolver: ConflictResolver) -> CatchUpBranch:
        process = Real.process()
        return CatchUpBranch(
            branches=GitBranches(process=process), workspace=GitWorkspace(process=process), resolver=resolver
        )

    def test_a_conflict_the_resolver_fixes_within_the_declared_files_gets_the_merge_concluded(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo_with_a_conflicting_edit_pushed_from_elsewhere(tmp_path)
        resolver = _EditingResolver(edits={"shared.txt": "resolved together\n"})

        result = self._action(resolver=resolver).execute(
            CatchUpBranchParams(
                repo=_REPO,
                issue=_ISSUE,
                slice_id=_SLICE_ID,
                worktree=str(repo),
                branch=self._SLICE_BRANCH,
                base=Git.BASE_BRANCH,
            )
        )

        assert result.outcome is Outcome.DONE
        assert not (repo / ".git" / "MERGE_HEAD").exists()
        assert Git.run(repo, "status", "--porcelain").strip() == ""
        assert (repo / "shared.txt").read_text() == "resolved together\n"

    def test_a_resolver_that_edits_a_file_outside_the_conflict_gets_the_merge_aborted(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_conflicting_edit_pushed_from_elsewhere(tmp_path)
        resolver = _EditingResolver(
            edits={"shared.txt": "resolved together\n", "clean.txt": "a stray edit outside the conflict\n"}
        )

        result = self._action(resolver=resolver).execute(
            CatchUpBranchParams(
                repo=_REPO,
                issue=_ISSUE,
                slice_id=_SLICE_ID,
                worktree=str(repo),
                branch=self._SLICE_BRANCH,
                base=Git.BASE_BRANCH,
            )
        )

        assert result.outcome is Outcome.HYGIENE_REJECTED
        assert not (repo / ".git" / "MERGE_HEAD").exists()
        assert (repo / "shared.txt").read_text() == "from the worktree\n"

    def test_a_file_already_dirty_before_the_merge_gets_the_merge_aborted_even_when_the_resolver_leaves_it_alone(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo_with_a_conflicting_edit_pushed_from_elsewhere(tmp_path)
        (repo / "clean.txt").write_text("left dirty by an earlier, unrelated call\n")
        resolver = _EditingResolver(edits={"shared.txt": "resolved together\n"})

        result = self._action(resolver=resolver).execute(
            CatchUpBranchParams(
                repo=_REPO,
                issue=_ISSUE,
                slice_id=_SLICE_ID,
                worktree=str(repo),
                branch=self._SLICE_BRANCH,
                base=Git.BASE_BRANCH,
            )
        )

        assert result.outcome is Outcome.HYGIENE_REJECTED
        assert not (repo / ".git" / "MERGE_HEAD").exists()
        assert (repo / "clean.txt").read_text() == "left dirty by an earlier, unrelated call\n"
