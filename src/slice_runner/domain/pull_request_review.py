from __future__ import annotations

from dataclasses import dataclass

from slice_runner.domain.pull_request_review_state import PullRequestReviewState


@dataclass(frozen=True, kw_only=True, slots=True)
class PullRequestReview:
    id: int
    state: PullRequestReviewState
    body: str
    comments: tuple[str, ...] = ()

    @property
    def asks_for_a_change(self) -> bool:
        return self._asks and bool(self.text)

    @property
    def text(self) -> str:
        return "\n\n".join(part.strip() for part in (self.body, *self.comments) if part.strip())

    @property
    def _asks(self) -> bool:
        match self.state:
            case PullRequestReviewState.PENDING | PullRequestReviewState.DISMISSED | PullRequestReviewState.APPROVED:
                return False
            case PullRequestReviewState.CHANGES_REQUESTED | PullRequestReviewState.COMMENTED:
                return True
