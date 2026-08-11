from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from slice_runner.domain.malformed_reason import MalformedReason
from slice_runner.domain.retry_response_kind import RetryResponseKind


@dataclass(frozen=True, kw_only=True, slots=True)
class RetryResponse:
    RETRY_TOKEN: ClassVar[str] = "-RETRY"

    kind: RetryResponseKind
    instruction: str = ""
    reason: MalformedReason | None = None

    @classmethod
    def of_the_comments(cls, comments: tuple[str, ...]) -> RetryResponse:
        for comment in reversed(comments):
            response = cls._of_the_comment(comment)
            if response is not None:
                return response

        return cls(kind=RetryResponseKind.NOT_YET)

    @classmethod
    def _of_the_comment(cls, comment: str) -> RetryResponse | None:
        stripped = comment.strip()
        if not stripped.startswith(cls.RETRY_TOKEN):
            return None

        instruction = stripped.removeprefix(cls.RETRY_TOKEN).strip()
        if not instruction:
            return cls(kind=RetryResponseKind.MALFORMED, reason=MalformedReason.MISSING_INSTRUCTION)

        return cls(kind=RetryResponseKind.RETRY, instruction=instruction)
