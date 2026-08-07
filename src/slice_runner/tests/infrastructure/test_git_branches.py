from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.infrastructure.git_branches import GitBranches, GitCommandFailedError
from slice_runner.tests.git_repo import Git
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestGitBranches:
    def test_a_branch_that_exists_is_reported_as_existing(self, tmp_path: Path) -> None:
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")

        exists = GitBranches(process=Real.process()).exists(worktree=str(repo), name=Git.BASE_BRANCH)

        assert exists is True

    def test_a_branch_that_does_not_exist_is_reported_as_absent(self, tmp_path: Path) -> None:
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")

        exists = GitBranches(process=Real.process()).exists(worktree=str(repo), name="slice/99-never-branched")

        assert exists is False

    def test_a_path_that_is_not_a_repo_raises_instead_of_answering_false(self, tmp_path: Path) -> None:
        outside = tmp_path / "not-a-repo"
        outside.mkdir()

        with pytest.raises(GitCommandFailedError):
            GitBranches(process=Real.process()).exists(worktree=str(outside), name=Git.BASE_BRANCH)


@pytest.mark.integration
class TestGitBranchesCreatingTheBranchOfTheSlice:
    _SLICE_BRANCH = "slice/16-el-loop-completo"

    @staticmethod
    def _repo_with_a_base_commit(tmp_path: Path) -> Path:
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")

        return repo

    def test_the_branch_of_the_slice_exists_after_creating_it(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_base_commit(tmp_path)
        branches = GitBranches(process=Real.process())

        branches.create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert branches.exists(worktree=str(repo), name=self._SLICE_BRANCH) is True

    def test_the_worktree_ends_standing_on_the_branch_it_created(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_base_commit(tmp_path)

        GitBranches(process=Real.process()).create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert Git.run(repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == self._SLICE_BRANCH

    def test_the_branch_starts_at_the_base_it_was_given_and_not_at_wherever_the_worktree_stood(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo_with_a_base_commit(tmp_path)
        Git.run(repo, "switch", "-c", "someone-elses-work")
        Git.run(repo, "commit", "--allow-empty", "-m", "work of another branch")

        GitBranches(process=Real.process()).create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert Git.run(repo, "rev-parse", "HEAD").strip() == Git.run(repo, "rev-parse", Git.BASE_BRANCH).strip()

    def test_a_branch_that_already_exists_raises_instead_of_silently_standing_on_the_old_one(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo_with_a_base_commit(tmp_path)
        branches = GitBranches(process=Real.process())
        branches.create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)
        Git.run(repo, "switch", Git.BASE_BRANCH)

        with pytest.raises(GitCommandFailedError, match=self._SLICE_BRANCH):
            branches.create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)
