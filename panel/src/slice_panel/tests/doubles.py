from __future__ import annotations

from typing import TYPE_CHECKING

from slice_panel.domain.follow_source import FollowSource

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from slice_panel.domain.follow_ended import FollowEnded
    from slice_panel.domain.follow_line import FollowLine


class ScriptedFollowSource(FollowSource):
    def __init__(self, *, lines: Sequence[FollowLine], ended: FollowEnded | None = None) -> None:
        self._lines = lines
        self._ended = ended

    async def events(self) -> AsyncIterator[FollowLine | FollowEnded]:
        for line in self._lines:
            yield line
        if self._ended is not None:
            yield self._ended
