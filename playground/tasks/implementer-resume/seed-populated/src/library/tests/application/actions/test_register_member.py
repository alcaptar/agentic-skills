from __future__ import annotations

from unittest.mock import Mock, create_autospec

import pytest

from library.application.actions.register_member import RegisterMember
from library.domain.exceptions import UnnamedMemberError
from library.domain.member_repository import MemberRepository
from library.tests.mothers.member_mother import MemberMother


class TestWhatRegisteringAMemberLeavesBehind:
    @staticmethod
    def _repository() -> Mock:
        return create_autospec(MemberRepository, spec_set=True, instance=True)

    def test_the_member_that_reaches_the_repository_carries_the_membership_it_was_asked_for(self) -> None:
        repository = self._repository()

        RegisterMember(repository=repository).execute(MemberMother.params())

        assert repository.save.call_args.args[0].membership == MemberMother.params().membership

    def test_a_member_whose_name_is_only_whitespace_is_refused_instead_of_stored_unnamed(self) -> None:
        repository = self._repository()

        with pytest.raises(UnnamedMemberError):
            RegisterMember(repository=repository).execute(MemberMother.params_without_a_name())

        assert repository.save.call_count == 0
