from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceCommitMessage:
    CO_AUTHOR: ClassVar[str] = "Co-Authored-By: Claude <noreply@anthropic.com>"

    subject: str

    def rendered(self) -> str:
        return "\n".join([self.subject, "", self.CO_AUTHOR])
