from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from slice_panel.domain.follow_ended import FollowEnded
    from slice_panel.domain.follow_line import FollowLine


class FollowSource(ABC):
    @abstractmethod
    def events(self) -> AsyncIterator[FollowLine | FollowEnded]: ...
