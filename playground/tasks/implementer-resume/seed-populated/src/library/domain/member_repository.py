from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from library.domain.member import Member


class MemberRepository(ABC):
    @abstractmethod
    def save(self, member: Member) -> None: ...
