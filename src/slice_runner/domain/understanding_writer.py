from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.alignment import Alignment
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.domain.understanding import Understanding


class UnderstandingWriter(ABC):
    @abstractmethod
    def write(
        self, *, subissue: SubIssue, parent: ParentIssue, repo: str, worktree: str, alignment: Alignment
    ) -> Understanding: ...
