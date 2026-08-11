from __future__ import annotations

from enum import StrEnum


class PrecheckOutcome(StrEnum):
    CLEAR = "clear"
    SLICE_IN_ANOTHER_REPO = "slice-in-another-repo"
    SUBISSUE_ALREADY_CLOSED = "subissue-already-closed"
    PULL_REQUEST_ALREADY_OPEN = "pull-request-already-open"
    BRANCH_ALREADY_EXISTS = "branch-already-exists"
    MISSING_SOURCES = "missing-sources"
    MISSING_CONTROLS = "missing-controls"
    BASE_NOT_ON_REMOTE = "base-not-on-remote"
