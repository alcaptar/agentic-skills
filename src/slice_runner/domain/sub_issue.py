from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.issue_label import IssueLabel
    from slice_runner.domain.issue_state import IssueState
    from slice_runner.domain.run import Run
    from slice_runner.domain.slice_identity import SliceIdentity


@dataclass(frozen=True, kw_only=True, slots=True)
class SubIssue:
    number: int
    slice_id: SliceIdentity
    summary: str
    title: str
    state: IssueState
    repo: str | None
    intention: str
    criteria: tuple[str, ...]
    signal: str
    excludes: str
    replaces: str
    run: Run | None
    label: IssueLabel | None

    @property
    def branch(self) -> str:
        return self.slice_id.branch

    @property
    def signal_is_exempt(self) -> bool:
        return self.signal.strip().lower().startswith("exenta")
