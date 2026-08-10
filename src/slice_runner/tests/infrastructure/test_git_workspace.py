from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from slice_runner.infrastructure.git_branches import GitCommandFailedError
from slice_runner.infrastructure.git_workspace import GitWorkspace
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.doubles import ScriptedProcess
from slice_runner.tests.git_repo import Git
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path

_WORKTREE = "/repos/agentic-skills"
_BRANCH = "slice/08-entrega-de-la-slice"
_TITLE = "feat(entrega-de-la-slice): commitear solo lo juzgado y abrir la pull request"


class TestTheCommandsGitWorkspaceRuns:
    def test_staging_names_every_path_after_a_double_dash_and_never_asks_git_to_pick_them(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout="", stderr=""), ProcessOutput(code=0, stdout="", stderr="")
        )

        GitWorkspace(process=process).stage(worktree=_WORKTREE, paths=("src/a.py", "src/tests/test_a.py"))

        assert process.calls[-1].argv == [
            "git",
            "-C",
            _WORKTREE,
            "add",
            "--",
            "src/a.py",
            "src/tests/test_a.py",
        ]
        for wildcard in ("-A", "--all", ".", "-u", "--update", ":/"):
            assert wildcard not in process.calls[-1].argv

    def test_it_asks_the_index_what_is_already_deleted_before_naming_the_paths_to_add(self) -> None:
        process = ScriptedProcess(
            ProcessOutput(code=0, stdout="", stderr=""), ProcessOutput(code=0, stdout="", stderr="")
        )

        GitWorkspace(process=process).stage(worktree=_WORKTREE, paths=("src/a.py",))

        assert process.calls[0].argv == [
            "git",
            "-C",
            _WORKTREE,
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=D",
        ]

    def test_the_index_is_read_against_head_so_it_is_what_the_commit_would_carry(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GitWorkspace(process=process).staged(worktree=_WORKTREE)

        assert process.calls[0].argv == ["git", "-C", _WORKTREE, "diff", "--cached", "--name-only"]

    def test_the_current_branch_comes_from_the_symbolic_ref_and_arrives_without_its_newline(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout=f"{_BRANCH}\n", stderr=""))

        branch = GitWorkspace(process=process).current_branch(worktree=_WORKTREE)

        assert branch == _BRANCH
        assert process.calls[0].argv == ["git", "-C", _WORKTREE, "symbolic-ref", "--short", "HEAD"]

    def test_committing_passes_the_message_as_one_argument_instead_of_letting_a_shell_split_it(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GitWorkspace(process=process).commit(worktree=_WORKTREE, message=_TITLE)

        assert process.calls[0].argv == ["git", "-C", _WORKTREE, "commit", "-m", _TITLE]

    def test_pushing_sets_the_upstream_so_the_branch_can_be_found_by_the_pull_request(self) -> None:
        process = ScriptedProcess(ProcessOutput(code=0, stdout="", stderr=""))

        GitWorkspace(process=process).push(worktree=_WORKTREE, branch=_BRANCH)

        assert process.calls[0].argv == ["git", "-C", _WORKTREE, "push", "-u", "origin", _BRANCH]


@pytest.mark.integration
class TestGitWorkspaceAgainstARealRepo:
    @staticmethod
    def _repo_with_a_commit(root: Path) -> Path:
        repo = Git.init_repo(root)
        (repo / "kept.py").write_text("x = 1\n", encoding="utf-8")
        Git.run(repo, "add", "--", "kept.py")
        Git.run(repo, "commit", "-m", "base")

        return repo

    def test_what_it_staged_is_what_it_reads_back_deletions_included(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")
        (repo / "added.py").write_text("y = 2\n", encoding="utf-8")
        (repo / "kept.py").unlink()
        workspace = GitWorkspace(process=Real.process())

        workspace.stage(worktree=str(repo), paths=("added.py", "kept.py"))

        assert workspace.staged(worktree=str(repo)) == ("added.py", "kept.py")

    def test_an_untouched_index_reads_back_empty_instead_of_one_blank_name(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")

        assert GitWorkspace(process=Real.process()).staged(worktree=str(repo)) == ()

    def test_a_path_that_is_not_in_the_repo_raises_instead_of_staging_nothing_in_silence(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")

        with pytest.raises(GitCommandFailedError, match=re.escape("never-written.py")):
            GitWorkspace(process=Real.process()).stage(worktree=str(repo), paths=("never-written.py",))

    def test_a_deletion_that_already_reached_the_index_does_not_abort_the_rest_of_the_round(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")
        (repo / "added.py").write_text("y = 2\n", encoding="utf-8")
        Git.run(repo, "rm", "--quiet", "kept.py")
        workspace = GitWorkspace(process=Real.process())

        workspace.stage(worktree=str(repo), paths=("added.py", "kept.py"))

        assert workspace.staged(worktree=str(repo)) == ("added.py", "kept.py")

    def test_a_round_whose_every_path_is_an_already_staged_deletion_stages_without_calling_git_add(
        self, tmp_path: Path
    ) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")
        Git.run(repo, "rm", "--quiet", "kept.py")
        workspace = GitWorkspace(process=Real.process())

        workspace.stage(worktree=str(repo), paths=("kept.py",))

        assert workspace.staged(worktree=str(repo)) == ("kept.py",)

    def test_the_branch_a_repo_is_on_is_the_one_it_reports(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")
        Git.run(repo, "checkout", "-b", _BRANCH)

        assert GitWorkspace(process=Real.process()).current_branch(worktree=str(repo)) == _BRANCH

    def test_a_detached_head_raises_instead_of_reporting_a_branch_name_nobody_is_on(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")
        Git.run(repo, "checkout", "--detach", "HEAD")

        with pytest.raises(GitCommandFailedError):
            GitWorkspace(process=Real.process()).current_branch(worktree=str(repo))

    def test_the_commit_it_writes_carries_the_message_and_only_what_was_staged(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")
        (repo / "added.py").write_text("y = 2\n", encoding="utf-8")
        (repo / "left-alone.py").write_text("z = 3\n", encoding="utf-8")
        workspace = GitWorkspace(process=Real.process())
        workspace.stage(worktree=str(repo), paths=("added.py",))

        workspace.commit(worktree=str(repo), message=_TITLE)

        assert Git.run(repo, "log", "-1", "--format=%s").strip() == _TITLE
        assert Git.run(repo, "show", "--name-only", "--format=", "HEAD").split() == ["added.py"]

    def test_nothing_to_commit_raises_instead_of_passing_for_a_commit_that_never_happened(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")

        with pytest.raises(GitCommandFailedError):
            GitWorkspace(process=Real.process()).commit(worktree=str(repo), message=_TITLE)

    def test_the_pushed_branch_lands_on_the_remote_pointing_at_the_commit_it_had_locally(self, tmp_path: Path) -> None:
        remote = tmp_path / "remote.git"
        Git.run(tmp_path, "init", "--bare", str(remote))
        repo = self._repo_with_a_commit(tmp_path / "repo")
        Git.run(repo, "checkout", "-b", _BRANCH)
        Git.run(repo, "remote", "add", "origin", str(remote))

        GitWorkspace(process=Real.process()).push(worktree=str(repo), branch=_BRANCH)

        assert Git.run(remote, "rev-parse", _BRANCH).strip() == Git.run(repo, "rev-parse", "HEAD").strip()

    def test_a_push_with_no_remote_to_push_to_raises_with_the_reason_git_gave(self, tmp_path: Path) -> None:
        repo = self._repo_with_a_commit(tmp_path / "repo")

        with pytest.raises(GitCommandFailedError, match="origin"):
            GitWorkspace(process=Real.process()).push(worktree=str(repo), branch=Git.BASE_BRANCH)
