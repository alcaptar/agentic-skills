from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from pathlib import Path


class Git:
    BASE_BRANCH: ClassVar[str] = "master"
    TIMEOUT_SECONDS: ClassVar[int] = 60

    @staticmethod
    def run(repo: Path, *args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=Git.TIMEOUT_SECONDS,
        )

        return done.stdout

    @classmethod
    def init_repo(cls, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        cls.run(root, "init", "-b", cls.BASE_BRANCH)

        return cls._identified(root)

    @classmethod
    def clone(cls, *, remote: Path, into: Path) -> Path:
        cls.run(into.parent, "clone", str(remote), str(into))

        return cls._identified(into)

    @classmethod
    def _identified(cls, root: Path) -> Path:
        cls.run(root, "config", "user.email", "t@example.com")
        cls.run(root, "config", "user.name", "test")

        return root

    @classmethod
    def repo_with_a_conflicting_edit_pushed_from_elsewhere(
        cls, tmp_path: Path, *, branch: str, extra_files: dict[str, str] | None = None
    ) -> tuple[Path, Path]:
        files = {"shared.txt": "base\n", **(extra_files or {})}
        remote = tmp_path / "remote.git"
        cls.run(tmp_path, "init", "--bare", str(remote))
        repo = cls.init_repo(tmp_path / "repo")
        for name, content in files.items():
            (repo / name).write_text(content)
        cls.run(repo, "add", *files)
        cls.run(repo, "commit", "-m", "base")
        cls.run(repo, "remote", "add", "origin", str(remote))
        cls.run(repo, "push", "-u", "origin", cls.BASE_BRANCH)
        cls.run(repo, "switch", "-c", branch, f"origin/{cls.BASE_BRANCH}")
        cls.run(repo, "push", "-u", "origin", branch)
        elsewhere = cls.clone(remote=remote, into=tmp_path / "elsewhere")
        cls.run(elsewhere, "switch", branch)
        (elsewhere / "shared.txt").write_text("from elsewhere\n")
        cls.run(elsewhere, "commit", "-am", "edited from elsewhere")
        cls.run(elsewhere, "push")

        return repo, remote
