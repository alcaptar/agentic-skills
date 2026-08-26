from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.domain.branch_catch_up_outcome import BranchCatchUpOutcome
from slice_runner.domain.exceptions import UnresolvableBaseError
from slice_runner.infrastructure.git_branches import GitBranches
from slice_runner.infrastructure.git_command_failed_error import GitCommandFailedError
from slice_runner.infrastructure.process import ProcessOutput, ProcessTimedOutError
from slice_runner.tests.doubles import RaisingOnCommand, ScriptedProcess, SpyingProcess
from slice_runner.tests.git_repo import Git
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path


class TestCommitsBehindRemoteWithTheReasonOnlyOnStdout:
    def test_the_message_carries_what_stdout_says_instead_of_the_bare_exit_code(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout="", stderr=""),
            ProcessOutput(code=1, stdout="fatal: ambiguous argument 'main..origin/main'", stderr=""),
        )

        with pytest.raises(UnresolvableBaseError, match="fatal: ambiguous argument"):
            GitBranches(process=process).commits_behind_remote(worktree="/repos/agentic-skills", base="main")


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


@pytest.mark.integration
class TestGitBranchesCatchingUpTheBranch:
    _SLICE_BRANCH = "slice/22-la-rama-se-pone-al-dia"

    @staticmethod
    def _repo_with_the_slice_branch_pushed(tmp_path: Path) -> tuple[Path, Path]:
        remote = tmp_path / "remote.git"
        Git.run(tmp_path, "init", "--bare", str(remote))
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")
        Git.run(repo, "remote", "add", "origin", str(remote))
        Git.run(repo, "push", "-u", "origin", Git.BASE_BRANCH)
        Git.run(repo, "switch", "-c", TestGitBranchesCatchingUpTheBranch._SLICE_BRANCH, f"origin/{Git.BASE_BRANCH}")
        Git.run(repo, "push", "-u", "origin", TestGitBranchesCatchingUpTheBranch._SLICE_BRANCH)

        return repo, remote

    def test_a_branch_left_behind_by_a_push_from_elsewhere_ends_up_at_the_remote_tip(self, tmp_path: Path) -> None:
        repo, remote = self._repo_with_the_slice_branch_pushed(tmp_path)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "switch", self._SLICE_BRANCH)
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "pushed from elsewhere")
        Git.run(elsewhere, "push")

        outcome = GitBranches(process=Real.process()).catch_up(
            worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
        )

        assert outcome.outcome is BranchCatchUpOutcome.CAUGHT_UP
        assert outcome.conflicting_paths == ()
        assert Git.run(repo, "rev-parse", "HEAD").strip() == Git.run(elsewhere, "rev-parse", self._SLICE_BRANCH).strip()

    def test_a_base_that_gained_commits_since_the_branch_was_born_is_merged_into_the_branch(
        self, tmp_path: Path
    ) -> None:
        repo, remote = self._repo_with_the_slice_branch_pushed(tmp_path)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "the base gained a commit")
        Git.run(elsewhere, "push")
        base_gain = Git.run(elsewhere, "rev-parse", Git.BASE_BRANCH).strip()

        outcome = GitBranches(process=Real.process()).catch_up(
            worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
        )

        assert outcome.outcome is BranchCatchUpOutcome.CAUGHT_UP
        Git.run(repo, "merge-base", "--is-ancestor", base_gain, "HEAD")

    def test_a_commit_the_branch_already_had_keeps_its_own_identifier_after_catching_up(self, tmp_path: Path) -> None:
        repo, remote = self._repo_with_the_slice_branch_pushed(tmp_path)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "switch", self._SLICE_BRANCH)
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "pushed from elsewhere")
        Git.run(elsewhere, "push")
        remote_commit = Git.run(elsewhere, "rev-parse", "HEAD").strip()
        Git.run(repo, "commit", "--allow-empty", "-m", "work already done locally")
        local_commit = Git.run(repo, "rev-parse", "HEAD").strip()

        outcome = GitBranches(process=Real.process()).catch_up(
            worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
        )

        assert outcome.outcome is BranchCatchUpOutcome.CAUGHT_UP
        assert Git.run(repo, "rev-parse", local_commit).strip() == local_commit
        Git.run(repo, "merge-base", "--is-ancestor", local_commit, "HEAD")
        Git.run(repo, "merge-base", "--is-ancestor", remote_commit, "HEAD")
        Git.run(repo, "push")

    @staticmethod
    def _repo_with_a_conflicting_edit_pushed_from_elsewhere(tmp_path: Path) -> tuple[Path, Path]:
        remote = tmp_path / "remote.git"
        Git.run(tmp_path, "init", "--bare", str(remote))
        repo = Git.init_repo(tmp_path / "repo")
        (repo / "shared.txt").write_text("base\n")
        Git.run(repo, "add", "shared.txt")
        Git.run(repo, "commit", "-m", "base")
        Git.run(repo, "remote", "add", "origin", str(remote))
        Git.run(repo, "push", "-u", "origin", Git.BASE_BRANCH)
        Git.run(repo, "switch", "-c", TestGitBranchesCatchingUpTheBranch._SLICE_BRANCH, f"origin/{Git.BASE_BRANCH}")
        Git.run(repo, "push", "-u", "origin", TestGitBranchesCatchingUpTheBranch._SLICE_BRANCH)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "switch", TestGitBranchesCatchingUpTheBranch._SLICE_BRANCH)
        (elsewhere / "shared.txt").write_text("from elsewhere\n")
        Git.run(elsewhere, "commit", "-am", "edited from elsewhere")
        Git.run(elsewhere, "push")

        return repo, remote

    def test_files_left_conflicting_close_the_merge_instead_of_leaving_the_worktree_half_merged(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_a_conflicting_edit_pushed_from_elsewhere(tmp_path)
        (repo / "shared.txt").write_text("from the worktree\n")
        Git.run(repo, "commit", "-am", "edited locally")

        outcome = GitBranches(process=Real.process()).catch_up(
            worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
        )

        assert outcome.outcome is BranchCatchUpOutcome.CONFLICTING
        assert Git.run(repo, "status", "--porcelain").strip() == ""
        assert not (repo / ".git" / "MERGE_HEAD").exists()

    def test_files_left_conflicting_report_the_paths_git_marked_as_unmerged(self, tmp_path: Path) -> None:
        repo, _ = self._repo_with_a_conflicting_edit_pushed_from_elsewhere(tmp_path)
        (repo / "shared.txt").write_text("from the worktree\n")
        Git.run(repo, "commit", "-am", "edited locally")

        outcome = GitBranches(process=Real.process()).catch_up(
            worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
        )

        assert outcome.conflicting_paths == ("shared.txt",)

    def test_a_failure_reading_the_conflicting_paths_still_aborts_the_merge_instead_of_leaving_it_half_merged(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_a_conflicting_edit_pushed_from_elsewhere(tmp_path)
        (repo / "shared.txt").write_text("from the worktree\n")
        Git.run(repo, "commit", "-am", "edited locally")
        process = RaisingOnCommand(
            when=("diff", "--name-only"), raises=ProcessTimedOutError("git diff: killed after 1s")
        )

        with pytest.raises(ProcessTimedOutError):
            GitBranches(process=process).catch_up(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert Git.run(repo, "status", "--porcelain").strip() == ""
        assert not (repo / ".git" / "MERGE_HEAD").exists()

    @staticmethod
    def _repo_with_a_conflicting_edit_on_a_non_ascii_named_file_pushed_from_elsewhere(
        tmp_path: Path,
    ) -> tuple[Path, Path]:
        remote = tmp_path / "remote.git"
        Git.run(tmp_path, "init", "--bare", str(remote))
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "config", "core.quotePath", "true")
        (repo / "conclusión.md").write_text("base\n")
        Git.run(repo, "add", "conclusión.md")
        Git.run(repo, "commit", "-m", "base")
        Git.run(repo, "remote", "add", "origin", str(remote))
        Git.run(repo, "push", "-u", "origin", Git.BASE_BRANCH)
        Git.run(repo, "switch", "-c", TestGitBranchesCatchingUpTheBranch._SLICE_BRANCH, f"origin/{Git.BASE_BRANCH}")
        Git.run(repo, "push", "-u", "origin", TestGitBranchesCatchingUpTheBranch._SLICE_BRANCH)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "switch", TestGitBranchesCatchingUpTheBranch._SLICE_BRANCH)
        (elsewhere / "conclusión.md").write_text("from elsewhere\n")
        Git.run(elsewhere, "commit", "-am", "edited from elsewhere")
        Git.run(elsewhere, "push")

        return repo, remote

    def test_a_conflicting_path_with_non_ascii_bytes_is_reported_literally_instead_of_octal_escaped(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_a_conflicting_edit_on_a_non_ascii_named_file_pushed_from_elsewhere(tmp_path)
        (repo / "conclusión.md").write_text("from the worktree\n")
        Git.run(repo, "commit", "-am", "edited locally")

        outcome = GitBranches(process=Real.process()).catch_up(
            worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
        )

        assert outcome.conflicting_paths == ("conclusión.md",)

    def test_a_branch_that_is_already_up_to_date_with_both_remotes_gains_no_merge_commit_and_makes_no_merge_call(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_the_slice_branch_pushed(tmp_path)
        before = Git.run(repo, "rev-parse", "HEAD").strip()
        spy = SpyingProcess()

        outcome = GitBranches(process=spy).catch_up(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert outcome.outcome is BranchCatchUpOutcome.CAUGHT_UP
        assert Git.run(repo, "rev-parse", "HEAD").strip() == before
        assert not spy.invoked("merge")

    @staticmethod
    def _repo_with_the_slice_branch_created_but_not_pushed(tmp_path: Path) -> tuple[Path, Path]:
        remote = tmp_path / "remote.git"
        Git.run(tmp_path, "init", "--bare", str(remote))
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")
        Git.run(repo, "remote", "add", "origin", str(remote))
        Git.run(repo, "push", "-u", "origin", Git.BASE_BRANCH)
        Git.run(repo, "switch", "-c", TestGitBranchesCatchingUpTheBranch._SLICE_BRANCH, f"origin/{Git.BASE_BRANCH}")

        return repo, remote

    def test_a_branch_never_pushed_to_its_own_remote_still_catches_up_from_the_base(self, tmp_path: Path) -> None:
        repo, remote = self._repo_with_the_slice_branch_created_but_not_pushed(tmp_path)
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "the base gained a commit")
        Git.run(elsewhere, "push")
        base_gain = Git.run(elsewhere, "rev-parse", Git.BASE_BRANCH).strip()

        outcome = GitBranches(process=Real.process()).catch_up(
            worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
        )

        assert outcome.outcome is BranchCatchUpOutcome.CAUGHT_UP
        Git.run(repo, "merge-base", "--is-ancestor", base_gain, "HEAD")

    def test_a_branch_never_pushed_to_its_own_remote_and_already_at_the_base_makes_no_merge_call(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_the_slice_branch_created_but_not_pushed(tmp_path)
        before = Git.run(repo, "rev-parse", "HEAD").strip()
        spy = SpyingProcess()

        outcome = GitBranches(process=spy).catch_up(worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH)

        assert outcome.outcome is BranchCatchUpOutcome.CAUGHT_UP
        assert Git.run(repo, "rev-parse", "HEAD").strip() == before
        assert not spy.invoked("merge")

    def test_uncommitted_changes_left_by_a_crashed_invocation_raise_instead_of_reporting_a_conflict(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_a_conflicting_edit_pushed_from_elsewhere(tmp_path)
        (repo / "shared.txt").write_text("uncommitted work left by a crash\n")

        with pytest.raises(GitCommandFailedError, match="overwritten by merge"):
            GitBranches(process=Real.process()).catch_up(
                worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
            )

    @staticmethod
    def _repo_with_the_branch_diverged_from_a_base_that_also_moved_on(tmp_path: Path) -> tuple[Path, Path]:
        repo, remote = TestGitBranchesCatchingUpTheBranch._repo_with_the_slice_branch_pushed(tmp_path)
        Git.run(repo, "commit", "--allow-empty", "-m", "work done on the branch")
        elsewhere = Git.clone(remote=remote, into=tmp_path / "elsewhere")
        Git.run(elsewhere, "commit", "--allow-empty", "-m", "the base moved on too")
        Git.run(elsewhere, "push")

        return repo, remote

    def test_a_machine_wide_merge_ff_only_setting_does_not_stop_a_genuine_merge_from_completing(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_the_branch_diverged_from_a_base_that_also_moved_on(tmp_path)
        Git.run(repo, "config", "merge.ff", "only")

        outcome = GitBranches(process=Real.process()).catch_up(
            worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
        )

        assert outcome.outcome is BranchCatchUpOutcome.CAUGHT_UP

    def test_a_machine_wide_commit_gpgsign_setting_with_no_usable_key_does_not_report_a_conflict(
        self, tmp_path: Path
    ) -> None:
        repo, _ = self._repo_with_the_branch_diverged_from_a_base_that_also_moved_on(tmp_path)
        Git.run(repo, "config", "commit.gpgsign", "true")
        Git.run(repo, "config", "user.signingkey", "not-a-real-key")

        outcome = GitBranches(process=Real.process()).catch_up(
            worktree=str(repo), name=self._SLICE_BRANCH, base=Git.BASE_BRANCH
        )

        assert outcome.outcome is BranchCatchUpOutcome.CAUGHT_UP
