from __future__ import annotations

from typing import ClassVar


class SliceRunnerCommands:
    EXECUTABLE: ClassVar[str] = "slice-runner"
    BASE: ClassVar[str] = "master"

    @classmethod
    def go(cls, *, repo: str, issue: int) -> tuple[str, ...]:
        return (cls.EXECUTABLE, "go", "--repo", repo, str(issue))

    @classmethod
    def review(cls, *, repo: str, issue: int, text: str) -> tuple[str, ...]:
        return (cls.EXECUTABLE, "review", "--repo", repo, str(issue), text)

    @classmethod
    def retry(cls, *, repo: str, issue: int, text: str) -> tuple[str, ...]:
        return (cls.EXECUTABLE, "retry", "--repo", repo, str(issue), text)

    @classmethod
    def status(cls, *, repo: str, parent: int) -> tuple[str, ...]:
        return (cls.EXECUTABLE, "status", "--repo", repo, "--json", str(parent))

    @classmethod
    def understanding(cls, *, repo: str, issue: int) -> tuple[str, ...]:
        return (cls.EXECUTABLE, "understanding", "--repo", repo, "--json", str(issue))

    @classmethod
    def run(cls, *, repo: str, parent: int, slice_id: str) -> tuple[str, ...]:
        return (cls.EXECUTABLE, "run", str(parent), "--repo", repo, "--base", cls.BASE, "--slice", slice_id)
