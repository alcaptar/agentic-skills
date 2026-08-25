from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from slice_runner.domain.merge_conflict import MergeConflict
from slice_runner.domain.source import Source, SourceKind


class MergeConflictMother:
    REPO: ClassVar[str] = "alcaptar/agentic-skills"
    ISSUE: ClassVar[int] = 38
    SLICE_ID: ClassVar[str] = "slice-04"
    WORKTREE: ClassVar[str] = "/repos/agentic-skills"
    BRANCH: ClassVar[str] = "slice/04-el-conflicto-de-contenido-lo-resuelve-un-agente"
    BASE: ClassVar[str] = "master"

    @classmethod
    def of_one_conflicted_file(cls) -> MergeConflict:
        return MergeConflict(
            repo=cls.REPO,
            issue=cls.ISSUE,
            slice_id=cls.SLICE_ID,
            worktree=cls.WORKTREE,
            branch=cls.BRANCH,
            base=cls.BASE,
            conflicted_paths=("shared.txt",),
            sources=(Source(kind=SourceKind.DOC, path="CLAUDE.md"),),
        )

    @classmethod
    def without_sources(cls) -> MergeConflict:
        return replace(cls.of_one_conflicted_file(), sources=())
