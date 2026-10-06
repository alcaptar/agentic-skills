from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, Self

from slice_panel.domain.slice_label import SliceLabel

if TYPE_CHECKING:
    from slice_panel.domain.follow_line import FollowLine
    from slice_panel.domain.slice_listing import SliceListing


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceView:
    RECENT: ClassVar[int] = 10
    CLOSED: ClassVar[str] = "closed"
    UNLABELLED: ClassVar[str] = "unlabelled"

    repo: str
    issue: int
    slice_id: str
    name: str | None
    parent: int | None
    latest: FollowLine | None
    recent: tuple[FollowLine, ...]
    listing: SliceListing | None = None

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

    @classmethod
    def listed(cls, listing: SliceListing) -> Self:
        return cls(
            repo=listing.repo,
            issue=listing.issue,
            slice_id=listing.slice_id,
            name=listing.name,
            parent=listing.parent,
            latest=None,
            recent=(),
            listing=listing,
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

    def with_listing(self, listing: SliceListing) -> Self:
        return replace(self, name=self.name or listing.name, parent=listing.parent, listing=listing)

    def status(self) -> str:
        if self.latest is not None:
            return self.latest.status
        if self.listing is not None and self.listing.closed:
            return self.CLOSED

        return self.UNLABELLED if self.listing is None or self.listing.label is None else self.listing.label

    def waits_for_alignment(self) -> bool:
        if self.latest is not None:
            return self.latest.awaits_a_person()

        return self.listing is not None and self.listing.label == SliceLabel.AWAITING_ALIGNMENT
