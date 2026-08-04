from __future__ import annotations


class InvalidVerdictError(ValueError):
    pass


class DiffNotBundlableError(ValueError):
    pass


class EmptyIndexError(DiffNotBundlableError):
    pass


class UnresolvableRepoOrBaseError(DiffNotBundlableError):
    pass
