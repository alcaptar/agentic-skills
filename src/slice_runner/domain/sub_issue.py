from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.issue_label import IssueLabel
    from slice_runner.domain.run import Run


@dataclass(frozen=True, kw_only=True, slots=True)
class SubIssue:
    number: int
    slice_id: str
    title: str
    repo: str | None
    run: Run | None
    label: IssueLabel | None
