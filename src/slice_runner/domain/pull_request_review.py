from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from slice_runner.domain.pull_request_review_state import PullRequestReviewState


@dataclass(frozen=True, kw_only=True, slots=True)
class PullRequestReview:
    CHANGE_TOKEN: ClassVar[str] = "-CHANGE"

    id: int
    state: PullRequestReviewState
    body: str
    comments: tuple[str, ...] = ()

    @property
    def submitted(self) -> bool:
        match self.state:
            case PullRequestReviewState.PENDING | PullRequestReviewState.DISMISSED:
                return False
            case (
                PullRequestReviewState.APPROVED
                | PullRequestReviewState.CHANGES_REQUESTED
                | PullRequestReviewState.COMMENTED
            ):
                return True

    @property
    def asks_for_a_change(self) -> bool:
        return self.submitted and any(part.strip().startswith(self.CHANGE_TOKEN) for part in self._parts)

    @property
    def text(self) -> str:
        return "\n\n".join(self._asked)

    @property
    def has_content(self) -> bool:
        return bool(self._asked)

    @property
    def _asked(self) -> tuple[str, ...]:
        return tuple(asked for asked in (self._without_the_token(part) for part in self._parts) if asked)

    @property
    def _parts(self) -> tuple[str, ...]:
        return (self.body, *self.comments)

    @classmethod
    def _without_the_token(cls, part: str) -> str:
        return part.strip().removeprefix(cls.CHANGE_TOKEN).strip()
