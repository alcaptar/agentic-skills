from __future__ import annotations

from slice_panel.domain.slice_view import SliceView
from slice_panel.tests.mothers.follow_line_mother import FollowLineMother


class SliceViewMother:
    @staticmethod
    def advancing() -> SliceView:
        return SliceView.first(FollowLineMother.advancing())

    @staticmethod
    def without_the_feature() -> SliceView:
        return SliceView.first(FollowLineMother.advancing_without_the_feature())
