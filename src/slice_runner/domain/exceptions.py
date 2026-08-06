from __future__ import annotations


class InvalidHarnessOutputError(ValueError):
    pass


class InvalidVerdictError(InvalidHarnessOutputError):
    pass


class InvalidImplementationReportError(ValueError):
    pass


class PermissionDeniedError(ValueError):
    pass


class ImpossibleTransitionError(ValueError):
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


class EmptyIssueBodyError(UnreadableIssueError):
    pass


class MalformedConventionLineError(UnreadableIssueError):
    pass


class LaggingSearchIndexError(ValueError):
    pass


class NoSliceLeftError(LookupError):
    pass
