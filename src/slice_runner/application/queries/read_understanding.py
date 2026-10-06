from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import NoUnderstandingPublishedError

if TYPE_CHECKING:
    from slice_runner.domain.run_repository import RunRepository


@dataclass(frozen=True, kw_only=True, slots=True)
class ReadUnderstandingParams:
    repo: str
    issue: int


class ReadUnderstanding:
    def __init__(self, *, repository: RunRepository) -> None:
        self._repository = repository

    def execute(self, params: ReadUnderstandingParams) -> str:
        understanding = self._repository.read_understanding(repo=params.repo, issue=params.issue)
        if not understanding:
            raise NoUnderstandingPublishedError(
                f"subissue #{params.issue} of {params.repo} has no understanding published"
            )

        return understanding
