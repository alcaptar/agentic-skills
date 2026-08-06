from __future__ import annotations

from enum import StrEnum
from typing import Self

from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.domain.pull_request_state import PullRequestState
from slice_runner.infrastructure.contract_model import ContractModel


class GhPullRequestState(StrEnum):
    MERGED = "MERGED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class GhPullRequestPayload(ContractModel):
    number: int

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable pull request", UnreadableForumError)


class GhPullRequestStatePayload(ContractModel):
    state: GhPullRequestState

    def to_domain(self) -> PullRequestState:
        match self.state:
            case GhPullRequestState.MERGED:
                return PullRequestState.MERGED
            case GhPullRequestState.OPEN:
                return PullRequestState.OPEN
            case GhPullRequestState.CLOSED:
                return PullRequestState.CLOSED

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "gh did not return a readable pull request state", UnreadableForumError)
