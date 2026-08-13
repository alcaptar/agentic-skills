from __future__ import annotations

from library.application.actions.register_member import RegisterMemberParams
from library.domain.membership import Membership


class MemberMother:
    @staticmethod
    def params() -> RegisterMemberParams:
        return RegisterMemberParams(member_id="m-1", name="Ada", membership=Membership.BASIC)

    @staticmethod
    def params_without_a_name() -> RegisterMemberParams:
        return RegisterMemberParams(member_id="m-2", name="   ", membership=Membership.PREMIUM)
