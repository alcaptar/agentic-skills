from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.pull_request_review_state import PullRequestReviewState


@dataclass(frozen=True, kw_only=True, slots=True)
class PullRequestReview:
    id: int
    state: PullRequestReviewState
    body: str
    comments: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return "\n\n".join(part.strip() for part in (self.body, *self.comments) if part.strip())

    @property
    def has_content(self) -> bool:
        return bool(self.text)
