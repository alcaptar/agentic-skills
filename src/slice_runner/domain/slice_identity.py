from __future__ import annotations

from dataclasses import dataclass

from slice_runner.domain.canonical_slice_id import CanonicalSliceId


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceIdentity:
    ordinal: int
    name: str
    user_story: str | None = None

    @property
    def canonical_id(self) -> CanonicalSliceId:
        return CanonicalSliceId.of_parts(ordinal=self.ordinal, user_story=self.user_story)

    @property
    def canonical(self) -> str:
        return self.canonical_id.text

    @property
    def branch(self) -> str:
        return f"slice/{self.canonical_id.branch_suffix}-{self.name}"
