from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Self

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, kw_only=True, slots=True)
class CoordinatorName:
    PREFIX: ClassVar[str] = "coordinador-"
    MAX_LENGTH: ClassVar[int] = 32
    ATTEMPTS: ClassVar[int] = 9
    REFUSED_CHARACTERS: ClassVar[re.Pattern[str]] = re.compile(r"[^a-z0-9_-]")

    base: str

    @classmethod
    def of_the_clone(cls, clone_root: Path) -> Self:
        folder = cls.REFUSED_CHARACTERS.sub("-", clone_root.name.lower())

        return cls(base=(cls.PREFIX + folder)[: cls.MAX_LENGTH])

    @property
    def candidates(self) -> tuple[str, ...]:
        suffixed = tuple(self._suffixed(attempt) for attempt in range(2, self.ATTEMPTS + 1))

        return (self.base, *suffixed)

    def _suffixed(self, attempt: int) -> str:
        suffix = f"-{attempt}"

        return self.base[: self.MAX_LENGTH - len(suffix)] + suffix
