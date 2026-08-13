from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.alignment_response import AlignmentResponse
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.issue_label import IssueLabel
    from slice_runner.domain.malformed_reason import MalformedReason
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.retry_response import RetryResponse
    from slice_runner.domain.run import Run
    from slice_runner.domain.sub_issue import SubIssue


class RunRepository(ABC):
    @abstractmethod
    def read_parent(self, *, repo: str, issue: int, slice_repo: str | None) -> ParentIssue: ...

    @abstractmethod
    def read_children(self, *, repo: str, parent: int, expected: int) -> tuple[SubIssue, ...]: ...

    @abstractmethod
    def read_understanding(self, *, repo: str, issue: int) -> str: ...

    @abstractmethod
    def read_alignment_response(self, *, repo: str, issue: int) -> AlignmentResponse: ...

    @abstractmethod
    def read_retry_instruction(self, *, repo: str, issue: int) -> RetryResponse: ...

    @abstractmethod
    def mark_reopened(self, *, repo: str, issue: int, instruction: str) -> None: ...

    @abstractmethod
    def write_malformed_response(self, *, repo: str, issue: int, reason: MalformedReason) -> None: ...

    @abstractmethod
    def write_run(self, *, repo: str, issue: int, run: Run) -> None: ...

    @abstractmethod
    def write_understanding(self, *, repo: str, issue: int, understanding: str) -> None: ...

    @abstractmethod
    def write_label(self, *, repo: str, issue: int, remove: IssueLabel | None, add: IssueLabel) -> None: ...

    @abstractmethod
    def remove_label(self, *, repo: str, issue: int, remove: IssueLabel) -> None: ...

    @abstractmethod
    def pause_for_alignment(self, *, repo: str, issue: int, remove: IssueLabel | None) -> None: ...

    @abstractmethod
    def flag_unmerged_pull_request(self, *, repo: str, issue: int, pull_request: int) -> None: ...

    @abstractmethod
    def close_parent(self, *, repo: str, issue: int, subissue_count: int) -> None: ...

    @abstractmethod
    def publish_findings(self, *, repo: str, issue: int, findings: tuple[Finding, ...]) -> None: ...

    @abstractmethod
    def find_finding(self, *, repo: str, issue: int, finding_id: str) -> Finding | None: ...
