from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.pull_request_status import PullRequestStatus


class Forum(ABC):
    @abstractmethod
    def open_pull_request(self, *, repo: str, branch: str) -> int | None: ...

    @abstractmethod
    def any_pull_request(self, *, repo: str, branch: str) -> int | None: ...

    @abstractmethod
    def create_pull_request(self, *, repo: str, branch: str, base: str, title: str, body: str) -> int: ...

    @abstractmethod
    def pull_request_state(self, *, repo: str, number: int) -> PullRequestStatus: ...

    @abstractmethod
    def authenticated_as(self) -> str | None: ...

    @abstractmethod
    def can_read(self, *, repo: str) -> bool: ...
