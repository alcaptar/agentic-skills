from __future__ import annotations


class InvalidVerdictError(ValueError):
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
