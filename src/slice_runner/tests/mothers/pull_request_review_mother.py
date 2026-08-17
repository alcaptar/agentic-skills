from __future__ import annotations

from slice_runner.domain.pull_request_review import PullRequestReview
from slice_runner.domain.pull_request_review_state import PullRequestReviewState


class PullRequestReviewMother:
    @classmethod
    def requesting_changes(
        cls, *, review_id: int = 101, body: str = "corrige el manejo de errores"
    ) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.CHANGES_REQUESTED, body=body)

    @classmethod
    def requesting_changes_with_no_content(cls, *, review_id: int = 101) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.CHANGES_REQUESTED, body="")

    @classmethod
    def approving(cls, *, review_id: int = 102) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.APPROVED, body="se ve bien")

    @classmethod
    def commenting(cls, *, review_id: int = 103) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.COMMENTED, body="una duda nada mas")

    @classmethod
    def still_pending(cls, *, review_id: int = 104) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.PENDING, body="")
