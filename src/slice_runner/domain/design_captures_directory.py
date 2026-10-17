from __future__ import annotations

from pathlib import PurePosixPath
from typing import ClassVar


class DesignCapturesDirectory:
    NAME: ClassVar[str] = ".design-captures"
    MANIFEST: ClassVar[str] = "manifest.json"
    COMPARISON: ClassVar[str] = "comparison.html"

    @classmethod
    def of(cls, worktree: str) -> str:
        return str(PurePosixPath(worktree) / cls.NAME)

    @classmethod
    def manifest_of(cls, worktree: str) -> str:
        return str(PurePosixPath(cls.of(worktree)) / cls.MANIFEST)

    @classmethod
    def comparison_of(cls, worktree: str) -> str:
        return cls.file_of(worktree, cls.COMPARISON)

    @classmethod
    def file_of(cls, worktree: str, name: str) -> str:
        return str(PurePosixPath(cls.of(worktree)) / name)

    @classmethod
    def exclusion(cls) -> str:
        return f"/{cls.NAME}/"
