from __future__ import annotations

from slice_runner.domain.pull_request_review import PullRequestReview
from slice_runner.domain.pull_request_review_state import PullRequestReviewState


class PullRequestReviewMother:
    @classmethod
    def asking_for_a_change(
        cls, *, review_id: int = 101, asked: str = "corrige el manejo de errores"
    ) -> PullRequestReview:
        return cls._commented(review_id=review_id, body=f"{PullRequestReview.CHANGE_TOKEN} {asked}")

    @classmethod
    def asking_for_a_change_in_a_line_comment(
        cls, *, review_id: int = 101, asked: str = "esta linea sobra"
    ) -> PullRequestReview:
        return cls._commented(review_id=review_id, body="", comments=(f"{PullRequestReview.CHANGE_TOKEN} {asked}",))

    @classmethod
    def asking_for_a_change_and_saying_more_without_the_token(
        cls, *, review_id: int = 101, asked: str = "esta linea sobra", also: str = "y de paso mira el nombre"
    ) -> PullRequestReview:
        return cls._commented(review_id=review_id, body=f"{PullRequestReview.CHANGE_TOKEN} {asked}", comments=(also,))

    @classmethod
    def asking_for_a_change_with_nothing_after_the_token(cls, *, review_id: int = 101) -> PullRequestReview:
        return cls._commented(review_id=review_id, body=PullRequestReview.CHANGE_TOKEN)

    @classmethod
    def just_talking(cls, *, review_id: int = 102) -> PullRequestReview:
        return cls._commented(review_id=review_id, body="una duda nada mas", comments=("por curiosidad",))

    @classmethod
    def requesting_changes_without_the_token(cls, *, review_id: int = 103) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.CHANGES_REQUESTED, body="esto no me gusta")

    @classmethod
    def requesting_changes_with_the_token(
        cls, *, review_id: int = 104, asked: str = "usa el value object"
    ) -> PullRequestReview:
        return PullRequestReview(
            id=review_id,
            state=PullRequestReviewState.CHANGES_REQUESTED,
            body=f"{PullRequestReview.CHANGE_TOKEN} {asked}",
        )

    @classmethod
    def approving(cls, *, review_id: int = 105) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.APPROVED, body="se ve bien")

    @classmethod
    def still_a_draft_carrying_the_token(cls, *, review_id: int = 106) -> PullRequestReview:
        return PullRequestReview(
            id=review_id,
            state=PullRequestReviewState.PENDING,
            body=f"{PullRequestReview.CHANGE_TOKEN} todavia lo estoy escribiendo",
        )

    @classmethod
    def dismissed_carrying_the_token(cls, *, review_id: int = 107) -> PullRequestReview:
        return PullRequestReview(
            id=review_id,
            state=PullRequestReviewState.DISMISSED,
            body=f"{PullRequestReview.CHANGE_TOKEN} esto ya se descarto",
        )

    @staticmethod
    def _commented(*, review_id: int, body: str, comments: tuple[str, ...] = ()) -> PullRequestReview:
        return PullRequestReview(id=review_id, state=PullRequestReviewState.COMMENTED, body=body, comments=comments)
