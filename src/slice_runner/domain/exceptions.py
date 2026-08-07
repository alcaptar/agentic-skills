from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend
    from slice_runner.domain.sub_issue import SubIssue


class MeasuredCallError(ValueError):
    spend: HarnessSpend | None = None


class InvalidHarnessOutputError(MeasuredCallError):
    pass


class InvalidVerdictError(InvalidHarnessOutputError):
    pass


class InvalidImplementationReportError(MeasuredCallError):
    pass


class PermissionDeniedError(MeasuredCallError):
    pass


class ImpossibleTransitionError(ValueError):
    pass


class RunNotClosedError(ValueError):
    pass


class UnreadableRunError(ValueError):
    pass


class DiffNotReadableError(ValueError):
    pass


class EmptyIndexError(DiffNotReadableError):
    pass


class UnresolvableRepoOrBaseError(DiffNotReadableError):
    pass


class DirtyIndexError(ValueError):
    pass


class ProtectedBranchError(ValueError):
    pass


class BranchMismatchError(ValueError):
    pass


class UnreadableIssueError(ValueError):
    pass


class UnreadableForumError(ValueError):
    pass


class NoPullRequestError(ValueError):
    pass


class EmptyIssueBodyError(UnreadableIssueError):
    pass


class MalformedConventionLineError(UnreadableIssueError):
    pass


class LaggingSearchIndexError(ValueError):
    pass


class NoSliceLeftError(LookupError):
    dangling: tuple[SubIssue, ...] = ()


class NoConversationRecordedError(LookupError):
    pass


class UnreadableCallTraceError(ValueError):
    pass


class ConversationNotFoundError(OSError):
    pass


class UnreadableConversationError(ValueError):
    pass
