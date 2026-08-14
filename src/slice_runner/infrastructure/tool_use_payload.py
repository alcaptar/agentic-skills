from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.domain.step import Step
from slice_runner.domain.unrecorded_conversation_cause import UnrecordedConversationCause
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.infrastructure.tool_use_log import HarnessCallToolUse, ToolUse, UnrecordedCallToolUse


class ToolUsePayload(ContractModel):
    turn: int
    tool: str
    path: str | None = None
    failed: bool | None = None

    @classmethod
    def from_domain(cls, use: ToolUse) -> Self:
        return cls(turn=use.turn, tool=use.tool, path=use.path, failed=use.failed or None)


class CallToolUsePayload(ContractModel):
    slice_id: str
    step: Step
    session: str
    uses: tuple[ToolUsePayload, ...]

    @classmethod
    def from_call(cls, call: HarnessCallToolUse) -> Self:
        return cls(
            slice_id=call.slice_id,
            step=call.step,
            session=call.session,
            uses=tuple(ToolUsePayload.from_domain(use) for use in call.uses),
        )


class UnrecordedCallToolUsePayload(ContractModel):
    slice_id: str
    step: Step
    session: str
    cause: UnrecordedConversationCause

    @classmethod
    def from_call(cls, call: UnrecordedCallToolUse) -> Self:
        return cls(slice_id=call.slice_id, step=call.step, session=call.session, cause=call.cause)
