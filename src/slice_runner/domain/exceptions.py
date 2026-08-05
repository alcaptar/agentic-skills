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
