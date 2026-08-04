from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.tests.git_repo import Git

if TYPE_CHECKING:
    from pathlib import Path


class RepoMother:
    @staticmethod
    def with_the_slice_staged(root: Path) -> Path:
        repo = Git.init_repo(root / "repo")
        (repo / "mod.py").write_text("def f() -> int:\n    return 1\n", encoding="utf-8")
        Git.run(repo, "add", "mod.py")
        Git.run(repo, "commit", "-m", "base")
        Git.run(repo, "switch", "-c", "slice/01-x")
        (repo / "mod.py").write_text("def f() -> int:\n    return 2\n", encoding="utf-8")
        Git.run(repo, "add", "mod.py")
        return repo

    @staticmethod
    def with_nothing_staged(root: Path) -> Path:
        repo = RepoMother.with_the_slice_staged(root)
        Git.run(repo, "reset", "--hard")
        return repo

    @staticmethod
    def outside_git(root: Path) -> Path:
        outside = root / "not-a-repo"
        outside.mkdir()
        return outside
