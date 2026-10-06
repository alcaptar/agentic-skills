from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from slice_panel.infrastructure.panel_app import PanelApp
from slice_panel.infrastructure.subprocess_follow_source import SubprocessFollowSource

if TYPE_CHECKING:
    from slice_panel.domain.follow_source import FollowSource


class Cli:
    FOLLOW_ARGV: ClassVar[tuple[str, ...]] = ("slice-runner", "follow", "--json")

    @classmethod
    def follow_source(cls) -> FollowSource:
        return SubprocessFollowSource(argv=cls.FOLLOW_ARGV)

    @classmethod
    def main(cls) -> int:
        PanelApp(source=cls.follow_source()).run()

        return 0
