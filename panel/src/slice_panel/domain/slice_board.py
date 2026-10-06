from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from slice_panel.domain.feature_group import FeatureGroup
from slice_panel.domain.slice_view import SliceView

if TYPE_CHECKING:
    from slice_panel.domain.follow_line import FollowLine
    from slice_panel.domain.slice_listing import SliceListing


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceBoard:
    slices: tuple[SliceView, ...] = ()

    def with_line(self, line: FollowLine) -> Self:
        known = self.slice_of(repo=line.repo, issue=line.issue)
        if known is None:
            return type(self)(slices=(*self.slices, SliceView.first(line)))

        return type(self)(slices=tuple(known.with_line(line) if each is known else each for each in self.slices))

    def with_listing(self, listing: SliceListing) -> Self:
        known = self.slice_of(repo=listing.repo, issue=listing.issue)
        if known is None:
            return type(self)(slices=(*self.slices, SliceView.listed(listing)))

        return type(self)(slices=tuple(known.with_listing(listing) if each is known else each for each in self.slices))

    def slice_of(self, *, repo: str, issue: int) -> SliceView | None:
        return next((each for each in self.slices if each.repo == repo and each.issue == issue), None)

    def groups(self) -> tuple[FeatureGroup, ...]:
        keys = sorted({(each.repo, each.parent) for each in self.slices}, key=self._order)

        return tuple(
            FeatureGroup(
                repo=repo,
                parent=parent,
                slices=tuple(
                    sorted(
                        (each for each in self.slices if (each.repo, each.parent) == (repo, parent)),
                        key=lambda each: each.slice_id,
                    )
                ),
            )
            for repo, parent in keys
        )

    @staticmethod
    def _order(key: tuple[str, int | None]) -> tuple[str, bool, int]:
        repo, parent = key

        return repo, parent is None, parent or 0
