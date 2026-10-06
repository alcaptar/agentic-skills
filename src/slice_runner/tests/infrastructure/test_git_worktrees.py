from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, ClassVar

import pytest

from slice_runner.domain.exceptions import WorktreeRetirementError
from slice_runner.domain.listed_worktree import ListedWorktree
from slice_runner.domain.slice_identity import SliceIdentity
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError
from slice_runner.infrastructure.git_worktrees import GitWorktrees
from slice_runner.tests.git_repo import Git
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestGitWorktrees:
    BRANCH: ClassVar[str] = "slice/01-the-slice"
    RULE: ClassVar[str] = SliceIdentity.worktrees_exclusion()

    @staticmethod
    def _remote(tmp_path: Path) -> Path:
        remote = tmp_path / "remote.git"
        Git.run(tmp_path, "init", "--bare", "-b", Git.BASE_BRANCH, str(remote))
        seed = Git.init_repo(tmp_path / "seed")
        Git.run(seed, "commit", "--allow-empty", "-m", "base")
        Git.run(seed, "remote", "add", "origin", str(remote))
        Git.run(seed, "push", "-u", "origin", Git.BASE_BRANCH)

        return remote

    @classmethod
    def _clone(cls, tmp_path: Path) -> Path:
        return Git.clone(remote=cls._remote(tmp_path), into=tmp_path / "clone")

    @staticmethod
    def _worktrees() -> GitWorktrees:
        return GitWorktrees(process=Real.process())

    @classmethod
    def _mounted(cls, clone: Path) -> Path:
        path = clone / SliceIdentity.WORKTREES_DIRECTORY / "01-the-slice"
        cls._worktrees().add_new_branch(root=str(clone), path=str(path), branch=cls.BRANCH, base=Git.BASE_BRANCH)

        return path

    def test_a_new_branch_is_created_from_the_remote_base_together_with_its_worktree(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)

        path = self._mounted(clone)

        assert Git.run(path, "branch", "--show-current").strip() == self.BRANCH
        assert Git.run(path, "rev-parse", "HEAD") == Git.run(clone, "rev-parse", f"origin/{Git.BASE_BRANCH}")

    def test_with_the_local_base_left_behind_by_a_push_from_elsewhere_the_new_branch_starts_at_the_remote_tip(
        self, tmp_path: Path
    ) -> None:
        remote = self._remote(tmp_path)
        clone = Git.clone(remote=remote, into=tmp_path / "clone")
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "pushed from elsewhere")
        Git.run(elsewhere, "push")

        path = self._mounted(clone)

        assert Git.run(path, "rev-parse", "HEAD") == Git.run(elsewhere, "rev-parse", Git.BASE_BRANCH)

    def test_creating_the_branch_leaves_the_local_base_branch_exactly_where_it_stood(self, tmp_path: Path) -> None:
        remote = self._remote(tmp_path)
        clone = Git.clone(remote=remote, into=tmp_path / "clone")
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "pushed from elsewhere")
        Git.run(elsewhere, "push")
        before = Git.run(clone, "rev-parse", Git.BASE_BRANCH)

        self._mounted(clone)

        assert Git.run(clone, "rev-parse", Git.BASE_BRANCH) == before

    def test_a_new_branch_whose_name_is_already_taken_raises_instead_of_standing_on_the_old_one(
        self, tmp_path: Path
    ) -> None:
        clone = self._clone(tmp_path)
        Git.run(clone, "branch", self.BRANCH)

        with pytest.raises(GitCommandFailedError, match=self.BRANCH):
            self._mounted(clone)

    def test_a_branch_that_already_exists_is_mounted_without_being_created_again(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        Git.run(clone, "branch", self.BRANCH)
        path = clone / ".worktrees" / "01-the-slice"

        self._worktrees().add_on_branch(root=str(clone), path=str(path), branch=self.BRANCH)

        assert Git.run(path, "branch", "--show-current").strip() == self.BRANCH

    def test_the_listing_marks_the_main_clone_apart_from_the_worktrees_and_gives_branches_without_their_prefix(
        self, tmp_path: Path
    ) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)

        listed = self._worktrees().listed(root=str(clone))

        assert listed == (
            ListedWorktree(path=str(clone.resolve()), branch=Git.BASE_BRANCH, prunable=False, main=True),
            ListedWorktree(path=str(path.resolve()), branch=self.BRANCH, prunable=False, main=False),
        )

    def test_the_listing_gives_no_branch_for_a_detached_worktree(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        detached = clone / ".worktrees" / "detached"
        Git.run(clone, "worktree", "add", "--detach", str(detached))

        listed = self._worktrees().listed(root=str(clone))

        assert [(entry.branch, entry.main) for entry in listed] == [(Git.BASE_BRANCH, True), ("", False)]

    def test_a_worktree_whose_directory_was_deleted_by_hand_is_listed_as_prunable_until_it_is_pruned(
        self, tmp_path: Path
    ) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)
        shutil.rmtree(path)

        before = self._worktrees().listed(root=str(clone))
        self._worktrees().prune(root=str(clone))
        after = self._worktrees().listed(root=str(clone))

        assert [entry.prunable for entry in before] == [False, True]
        assert [entry.branch for entry in after] == [Git.BASE_BRANCH]

    def test_a_branch_that_exists_is_told_apart_from_one_that_does_not(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        Git.run(clone, "branch", self.BRANCH)

        worktrees = self._worktrees()

        assert (
            worktrees.branch_exists(root=str(clone), name=self.BRANCH),
            worktrees.branch_exists(root=str(clone), name="slice/99-never-branched"),
        ) == (True, False)

    def test_asking_about_a_branch_outside_any_repo_raises_instead_of_answering_false(self, tmp_path: Path) -> None:
        outside = tmp_path / "not-a-repo"
        outside.mkdir()

        with pytest.raises(GitCommandFailedError):
            self._worktrees().branch_exists(root=str(outside), name=Git.BASE_BRANCH)

    def test_the_rule_is_written_into_the_exclusion_of_the_clone_and_the_directory_stops_showing_as_untracked(
        self, tmp_path: Path
    ) -> None:
        clone = self._clone(tmp_path)
        self._mounted(clone)
        assert ".worktrees/" in Git.run(clone, "status", "--porcelain")

        self._worktrees().exclude(root=str(clone), rule=self.RULE)

        assert (clone / ".git" / "info" / "exclude").read_text().splitlines().count(self.RULE) == 1
        assert Git.run(clone, "status", "--porcelain") == ""

    def test_writing_the_rule_again_does_not_duplicate_it(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        worktrees = self._worktrees()

        worktrees.exclude(root=str(clone), rule=self.RULE)
        worktrees.exclude(root=str(clone), rule=self.RULE)

        assert (clone / ".git" / "info" / "exclude").read_text().splitlines().count(self.RULE) == 1

    def test_the_rule_goes_to_the_common_directory_of_the_clone_even_when_asked_from_inside_a_worktree(
        self, tmp_path: Path
    ) -> None:
        clone = self._clone(tmp_path)
        inside = self._mounted(clone)
        assert (inside / ".git").is_file()

        self._worktrees().exclude(root=str(inside), rule=self.RULE)

        assert (clone / ".git" / "info" / "exclude").read_text().splitlines().count(self.RULE) == 1
        assert Git.run(clone, "status", "--porcelain") == ""

    def test_the_common_directory_of_a_worktree_is_the_git_directory_of_its_clone(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        inside = self._mounted(clone)
        worktrees = self._worktrees()

        assert worktrees.common_dir(path=str(inside)) == worktrees.common_dir(path=str(clone))
        assert worktrees.common_dir(path=str(clone)) == str((clone / ".git").resolve())

    def test_a_path_that_is_inside_no_repo_has_no_common_directory(self, tmp_path: Path) -> None:
        outside = tmp_path / "not-a-repo"
        outside.mkdir()

        assert self._worktrees().common_dir(path=str(outside)) == ""
        assert self._worktrees().common_dir(path=str(tmp_path / "does-not-exist")) == ""

    def test_asking_to_mount_over_a_path_that_git_refuses_raises_instead_of_pretending(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        occupied = clone / ".worktrees" / "01-the-slice"
        occupied.mkdir(parents=True)
        (occupied / "file.txt").write_text("not a worktree")

        with pytest.raises(GitCommandFailedError):
            self._worktrees().add_new_branch(
                root=str(clone), path=str(occupied), branch=self.BRANCH, base=Git.BASE_BRANCH
            )

    def test_a_clean_tree_has_no_uncommitted_work(self, tmp_path: Path) -> None:
        path = self._mounted(self._clone(tmp_path))

        assert self._worktrees().has_uncommitted_work(path=str(path)) is False

    def test_a_modified_tracked_file_is_uncommitted_work(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)
        (path / "tracked.txt").write_text("one")
        Git.run(path, "add", "tracked.txt")
        Git.run(path, "commit", "-m", "track it")
        (path / "tracked.txt").write_text("two")

        assert self._worktrees().has_uncommitted_work(path=str(path)) is True

    def test_a_file_git_does_not_track_yet_is_uncommitted_work_too(self, tmp_path: Path) -> None:
        path = self._mounted(self._clone(tmp_path))
        (path / "new.txt").write_text("nobody added me")

        assert self._worktrees().has_uncommitted_work(path=str(path)) is True

    def test_a_staged_file_is_uncommitted_work(self, tmp_path: Path) -> None:
        path = self._mounted(self._clone(tmp_path))
        (path / "staged.txt").write_text("staged")
        Git.run(path, "add", "staged.txt")

        assert self._worktrees().has_uncommitted_work(path=str(path)) is True

    def test_asking_about_a_path_that_is_no_worktree_raises_instead_of_answering_that_nothing_is_there(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(WorktreeRetirementError):
            self._worktrees().has_uncommitted_work(path=str(tmp_path / "does-not-exist"))

    def test_a_tree_of_the_slice_on_its_path_is_mounted(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)

        assert self._worktrees().is_mounted(root=str(clone), path=str(path), branch=self.BRANCH) is True

    def test_a_path_with_no_tree_on_it_is_not_mounted(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)

        mounted = self._worktrees().is_mounted(root=str(clone), path=str(clone / "nothing"), branch=self.BRANCH)

        assert mounted is False

    def test_a_tree_on_that_path_holding_another_branch_is_not_mounted_for_this_one(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)

        assert self._worktrees().is_mounted(root=str(clone), path=str(path), branch="slice/00-other") is False

    def test_asking_whether_a_tree_is_mounted_outside_any_repo_raises_instead_of_answering_false(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(WorktreeRetirementError):
            self._worktrees().is_mounted(root=str(tmp_path), path=str(tmp_path / "x"), branch=self.BRANCH)

    def test_a_branch_cut_from_the_base_with_no_commit_of_its_own_has_nothing_only_local(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        self._mounted(clone)

        assert self._worktrees().local_only_commits(root=str(clone), branch=self.BRANCH) == 0

    def test_every_commit_that_no_remote_has_counts_as_only_local(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)
        Git.run(path, "commit", "--allow-empty", "-m", "one")
        Git.run(path, "commit", "--allow-empty", "-m", "two")

        assert self._worktrees().local_only_commits(root=str(clone), branch=self.BRANCH) == 2

    def test_a_commit_that_was_pushed_is_no_longer_only_local(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)
        Git.run(path, "commit", "--allow-empty", "-m", "one")
        Git.run(path, "push", "origin", self.BRANCH)
        Git.run(path, "commit", "--allow-empty", "-m", "two")

        assert self._worktrees().local_only_commits(root=str(clone), branch=self.BRANCH) == 1

    def test_asking_about_a_branch_that_does_not_exist_raises_instead_of_answering_zero(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)

        with pytest.raises(WorktreeRetirementError):
            self._worktrees().local_only_commits(root=str(clone), branch="slice/99-not-there")

    def test_removing_a_clean_tree_takes_its_directory_and_its_registration_away(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)

        self._worktrees().remove(root=str(clone), path=str(path))

        assert not path.exists()
        assert [entry.path for entry in self._worktrees().listed(root=str(clone))] == [str(clone.resolve())]

    def test_removing_a_tree_with_uncommitted_work_is_refused_by_git_and_leaves_it_in_place(
        self, tmp_path: Path
    ) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)
        (path / "precious.txt").write_text("not committed")

        with pytest.raises(WorktreeRetirementError):
            self._worktrees().remove(root=str(clone), path=str(path))

        assert (path / "precious.txt").read_text() == "not committed"

    def test_deleting_the_branch_of_a_tree_that_is_gone_removes_it_from_the_clone(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)
        path = self._mounted(clone)
        Git.run(path, "commit", "--allow-empty", "-m", "never pushed")
        worktrees = self._worktrees()
        worktrees.remove(root=str(clone), path=str(path))

        worktrees.delete_branch(root=str(clone), branch=self.BRANCH)

        assert worktrees.branch_exists(root=str(clone), name=self.BRANCH) is False

    def test_deleting_a_branch_that_does_not_exist_raises(self, tmp_path: Path) -> None:
        clone = self._clone(tmp_path)

        with pytest.raises(WorktreeRetirementError):
            self._worktrees().delete_branch(root=str(clone), branch="slice/99-not-there")
