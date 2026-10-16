from __future__ import annotations

from slice_runner.domain.exceptions import UnreadableFollowLineError
from slice_runner.infrastructure.follow_activity_v2_payload import FollowActivityV2Payload
from slice_runner.infrastructure.follow_transition_v2_payload import FollowTransitionV2Payload


class FollowLineV2Payload:
    @staticmethod
    def from_contract(data: dict[str, object]) -> FollowTransitionV2Payload | FollowActivityV2Payload:
        kind = data.get("kind")
        if kind == "transition":
            return FollowTransitionV2Payload.from_contract(data)
        if kind == "activity":
            return FollowActivityV2Payload.from_contract(data)

        raise UnreadableFollowLineError(f"follow line v2: `kind` is not a known kind (got {kind!r})")
