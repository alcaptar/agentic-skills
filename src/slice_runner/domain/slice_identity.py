from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceIdentity:
    ordinal: int
    name: str
    user_story: str | None = None

    @property
    def canonical(self) -> str:
        if self.user_story is None:
            return f"slice-{self.ordinal:02d}"

        return f"{self.user_story}-{self.ordinal:02d}"

    @property
    def branch(self) -> str:
        return f"slice/{self.canonical.removeprefix('slice-')}-{self.name}"
