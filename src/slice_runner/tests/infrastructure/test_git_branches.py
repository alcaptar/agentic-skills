from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slice_runner.infrastructure.git_branches import GitBranches, GitCommandFailedError
from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.tests.git_repo import Git

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
class TestGitBranches:
    def test_a_branch_that_exists_is_reported_as_existing(self, tmp_path: Path) -> None:
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")

        exists = GitBranches(process=LocalProcess()).exists(worktree=str(repo), name=Git.BASE_BRANCH)

        assert exists is True

    def test_a_branch_that_does_not_exist_is_reported_as_absent(self, tmp_path: Path) -> None:
        repo = Git.init_repo(tmp_path / "repo")
        Git.run(repo, "commit", "--allow-empty", "-m", "base")

        exists = GitBranches(process=LocalProcess()).exists(worktree=str(repo), name="slice/99-never-branched")

        assert exists is False

    def test_a_path_that_is_not_a_repo_raises_instead_of_answering_false(self, tmp_path: Path) -> None:
        outside = tmp_path / "not-a-repo"
        outside.mkdir()

        with pytest.raises(GitCommandFailedError):
            GitBranches(process=LocalProcess()).exists(worktree=str(outside), name=Git.BASE_BRANCH)
