from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.exceptions import UnresolvableBaseError
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
    def _repo_with_a_base_commit(tmp_path: Path) -> tuple[Path, Path]:
        remote = tmp_path / "remote.git"
        Git.run(tmp_path, "init", "--bare", str(remote))
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")
        Git.run(repo, "remote", "add", "origin", str(remote))
        Git.run(repo, "push", "-u", "origin", Git.BASE_BRANCH)

        return repo, remote

    def test_the_branch_of_the_slice_exists_after_creating_it(self, tmp_path: Path) -> None:
        repo, _ = self._repo_with_a_base_commit(tmp_path)
        branches = GitBranches(process=Real.process())

        branches.create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert branches.exists(worktree=str(repo), name=self._SLICE_BRANCH) is True

    def test_the_worktree_ends_standing_on_the_branch_it_created(self, tmp_path: Path) -> None:
        repo, _ = self._repo_with_a_base_commit(tmp_path)

        GitBranches(process=Real.process()).create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert Git.run(repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == self._SLICE_BRANCH

    def test_the_branch_starts_at_the_base_it_was_given_and_not_at_wherever_the_worktree_stood(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_a_base_commit(tmp_path)
        Git.run(repo, "switch", "-c", "someone-elses-work")
        Git.run(repo, "commit", "--allow-empty", "-m", "work of another branch")

        GitBranches(process=Real.process()).create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert Git.run(repo, "rev-parse", "HEAD").strip() == Git.run(repo, "rev-parse", Git.BASE_BRANCH).strip()

    def test_a_branch_that_already_exists_raises_instead_of_silently_standing_on_the_old_one(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_a_base_commit(tmp_path)
        branches = GitBranches(process=Real.process())
        branches.create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)
        Git.run(repo, "switch", Git.BASE_BRANCH)

        with pytest.raises(GitCommandFailedError, match=self._SLICE_BRANCH):
            branches.create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

    def test_with_the_local_base_left_behind_by_a_push_from_elsewhere_the_worktree_ends_up_at_the_remote_tip(
        self, tmp_path: Path
    ) -> None:
        repo, remote = self._repo_with_a_base_commit(tmp_path)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "pushed from elsewhere")
        Git.run(elsewhere, "push")

        GitBranches(process=Real.process()).create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert Git.run(repo, "rev-parse", "HEAD").strip() == Git.run(elsewhere, "rev-parse", Git.BASE_BRANCH).strip()

    def test_creating_the_branch_leaves_the_local_base_branch_exactly_where_it_stood(self, tmp_path: Path) -> None:
        repo, remote = self._repo_with_a_base_commit(tmp_path)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "pushed from elsewhere")
        Git.run(elsewhere, "push")
        before = Git.run(repo, "rev-parse", Git.BASE_BRANCH).strip()

        GitBranches(process=Real.process()).create(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert Git.run(repo, "rev-parse", Git.BASE_BRANCH).strip() == before


@pytest.mark.integration
class TestGitBranchesComparingABaseAgainstItsRemote:
    @staticmethod
    def _repo_pushed_to_a_bare_remote(tmp_path: Path) -> tuple[Path, Path]:
        remote = tmp_path / "remote.git"
        Git.run(tmp_path, "init", "--bare", str(remote))
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")
        Git.run(repo, "remote", "add", "origin", str(remote))
        Git.run(repo, "push", "-u", "origin", Git.BASE_BRANCH)

        return repo, remote

    def test_a_base_that_matches_its_remote_reports_zero_commits_behind(self, tmp_path: Path) -> None:
        repo, _ = self._repo_pushed_to_a_bare_remote(tmp_path)

        behind = GitBranches(process=Real.process()).commits_behind_remote(worktree=str(repo), base=Git.BASE_BRANCH)

        assert behind == 0

    def test_a_base_left_behind_by_a_push_from_elsewhere_reports_how_many_commits_it_is_missing(
        self, tmp_path: Path
    ) -> None:
        repo, remote = self._repo_pushed_to_a_bare_remote(tmp_path)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "pushed from elsewhere")
        Git.run(elsewhere, "push")

        behind = GitBranches(process=Real.process()).commits_behind_remote(worktree=str(repo), base=Git.BASE_BRANCH)

        assert behind == 1

    def test_comparing_the_base_fetches_first_so_a_push_nobody_fetched_by_hand_is_still_seen(
        self, tmp_path: Path
    ) -> None:
        repo, remote = self._repo_pushed_to_a_bare_remote(tmp_path)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "pushed from elsewhere")
        Git.run(elsewhere, "push")

        behind = GitBranches(process=Real.process()).commits_behind_remote(worktree=str(repo), base=Git.BASE_BRANCH)

        assert behind > 0

    def test_comparing_the_base_only_updates_the_remote_tracking_refs_and_leaves_the_local_branch_untouched(
        self, tmp_path: Path
    ) -> None:
        repo, remote = self._repo_pushed_to_a_bare_remote(tmp_path)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "pushed from elsewhere")
        Git.run(elsewhere, "push")
        before = Git.run(repo, "rev-parse", Git.BASE_BRANCH).strip()

        GitBranches(process=Real.process()).commits_behind_remote(worktree=str(repo), base=Git.BASE_BRANCH)

        assert Git.run(repo, "rev-parse", Git.BASE_BRANCH).strip() == before

    def test_a_worktree_with_no_remote_to_fetch_from_raises_with_the_reason_git_gave(self, tmp_path: Path) -> None:
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")

        with pytest.raises(GitCommandFailedError):
            GitBranches(process=Real.process()).commits_behind_remote(worktree=str(repo), base=Git.BASE_BRANCH)

    def test_a_base_that_exists_locally_but_was_never_pushed_raises_naming_the_base_instead_of_a_git_command_failure(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_pushed_to_a_bare_remote(tmp_path)
        Git.run(repo, "switch", "-c", "slice/05-never-pushed")

        with pytest.raises(UnresolvableBaseError, match="slice/05-never-pushed"):
            GitBranches(process=Real.process()).commits_behind_remote(worktree=str(repo), base="slice/05-never-pushed")

    def test_a_base_that_does_not_exist_anywhere_raises_naming_the_base_instead_of_a_git_command_failure(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_pushed_to_a_bare_remote(tmp_path)

        with pytest.raises(UnresolvableBaseError, match="never-existed"):
            GitBranches(process=Real.process()).commits_behind_remote(worktree=str(repo), base="never-existed")
