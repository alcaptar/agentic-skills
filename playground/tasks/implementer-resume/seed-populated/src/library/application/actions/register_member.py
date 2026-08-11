from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from library.domain.exceptions import UnnamedMemberError
from library.domain.member import Member

if TYPE_CHECKING:
    from library.domain.member_repository import MemberRepository
    from library.domain.membership import Membership


@dataclass(frozen=True, kw_only=True, slots=True)
class RegisterMemberParams:
    member_id: str
    name: str
    membership: Membership


class RegisterMember:
    def __init__(self, *, repository: MemberRepository) -> None:
        self._repository = repository

    def execute(self, params: RegisterMemberParams) -> Member:
        if not params.name.strip():
            raise UnnamedMemberError(params.member_id)

        member = Member(member_id=params.member_id, name=params.name, membership=params.membership)
        self._repository.save(member)

        return member
