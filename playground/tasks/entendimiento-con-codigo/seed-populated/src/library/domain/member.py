from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from library.domain.membership import Membership


@dataclass(frozen=True, kw_only=True, slots=True)
class Member:
    member_id: str
    name: str
    membership: Membership
