from __future__ import annotations

from typing import ClassVar, Literal, Self

from slice_runner.domain.exceptions import UnreadableFollowLineError
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.follow_actor import FollowActor


class FollowActivityV2Payload(ContractModel):
    VERSION: ClassVar[int] = 2

    version: Literal[2]
    kind: Literal["activity"]
    ts: int
    repo: str
    issue: int
    slice_id: str
    actor: FollowActor
    tool: str
    target: str

    @classmethod
    def from_contract(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "follow line v2 activity", UnreadableFollowLineError)
