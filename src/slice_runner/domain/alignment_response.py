from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from slice_runner.domain.alignment_response_kind import AlignmentResponseKind
from slice_runner.domain.malformed_reason import MalformedReason


@dataclass(frozen=True, kw_only=True, slots=True)
class AlignmentResponse:
    GO_TOKEN: ClassVar[str] = "-GO"
    REVIEW_TOKEN: ClassVar[str] = "-REVIEW"

    kind: AlignmentResponseKind
    correction: str = ""
    reason: MalformedReason | None = None

    @classmethod
    def of_the_comments(cls, comments: tuple[str, ...]) -> AlignmentResponse:
        for comment in reversed(comments):
            response = cls._of_the_comment(comment)
            if response is not None:
                return response

        return cls(kind=AlignmentResponseKind.NOT_YET)

    @classmethod
    def _of_the_comment(cls, comment: str) -> AlignmentResponse | None:
        stripped = comment.strip()
        if stripped == cls.GO_TOKEN:
            return cls(kind=AlignmentResponseKind.GO)
        if stripped.startswith(cls.GO_TOKEN):
            return cls(kind=AlignmentResponseKind.MALFORMED, reason=MalformedReason.GO_CARRIES_TEXT)
        if stripped.startswith(cls.REVIEW_TOKEN):
            correction = stripped.removeprefix(cls.REVIEW_TOKEN).strip()
            if correction:
                return cls(kind=AlignmentResponseKind.REVIEW, correction=correction)

            return cls(kind=AlignmentResponseKind.MALFORMED, reason=MalformedReason.MISSING_CORRECTION)

        return None
