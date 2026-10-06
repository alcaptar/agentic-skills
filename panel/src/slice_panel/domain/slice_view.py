from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, Self

if TYPE_CHECKING:
    from slice_panel.domain.follow_line import FollowLine


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceView:
    RECENT: ClassVar[int] = 10

    repo: str
    issue: int
    slice_id: str
    name: str | None
    parent: int | None
    latest: FollowLine
    recent: tuple[FollowLine, ...]

    @classmethod
    def first(cls, line: FollowLine) -> Self:
        return cls(
            repo=line.repo,
            issue=line.issue,
            slice_id=line.slice_id,
            name=line.name,
            parent=line.parent,
            latest=line,
            recent=(line,),
        )

    def with_line(self, line: FollowLine) -> Self:
        recent = tuple(sorted((*self.recent, line), key=lambda each: each.ts))[-self.RECENT :]

        return replace(
            self,
            slice_id=line.slice_id,
            name=line.name or self.name,
            parent=self.parent if line.parent is None else line.parent,
            latest=recent[-1],
            recent=recent,
        )

    def awaits_a_person(self) -> bool:
        return self.latest.awaits_a_person()
