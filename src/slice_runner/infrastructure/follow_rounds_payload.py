from __future__ import annotations

from slice_runner.infrastructure.contract_model import ContractModel


class FollowRoundPayload(ContractModel):
    used: int
    limit: int


class FollowRoundsPayload(ContractModel):
    controls: FollowRoundPayload
    hygiene: FollowRoundPayload
    judge: FollowRoundPayload
    ci: FollowRoundPayload
    ci_indeterminate: FollowRoundPayload
    catch_up: FollowRoundPayload
