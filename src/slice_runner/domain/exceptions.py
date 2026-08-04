from __future__ import annotations


class InvalidVerdictError(ValueError):
    pass


class DiffNotWrittenError(ValueError):
    pass


class EmptyIndexError(DiffNotWrittenError):
    pass


class UnresolvableRepoOrBaseError(DiffNotWrittenError):
    pass
