from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.domain.call_trace import HarnessCall
from slice_runner.domain.exceptions import PermissionDeniedError, UnreadableConversationError
from slice_runner.domain.implementation import Implementation
from slice_runner.domain.implementer import Implementer
from slice_runner.domain.step import Step
from slice_runner.infrastructure.conversation_transcript import TranscriptToolUseBlock
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.report_payload import ImplementationReportPayload
from slice_runner.infrastructure.turn_log import HarnessTurn

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.infrastructure.process import Process
    from slice_runner.infrastructure.turn_log import TurnLog


class ClaudeImplementer(Implementer):
    def __init__(self, *, process: Process, trace: CallTrace, turns: TurnLog, spend_log: CallSpendLog) -> None:
        self._process = process
        self._trace = trace
        self._turns = turns
        self._spend_log = spend_log

    def implement(self, assignment: Assignment) -> Implementation:
        invocation = ImplementerInvocation(assignment=assignment)
        watch = _TurnWatch(turns=self._turns, slice_id=assignment.slice_id)
        output = self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd, on_line=watch)
        envelope = HarnessOutput.from_process(output)
        self._trace.record(HarnessCall(slice_id=assignment.slice_id, step=Step.IMPLEMENT, session=envelope.session_id))
        spend = envelope.to_domain()
        self._spend_log.record(HarnessCallSpend(session=envelope.session_id, spend=spend))
        with envelope.measuring():
            self._reject_denials(envelope)
            report = ImplementationReportPayload.from_dict(envelope.structured_output)

        return Implementation(paths=report.to_domain(), left_out=tuple(report.left_out), spend=spend)

    @staticmethod
    def _reject_denials(envelope: HarnessOutput) -> None:
        denials = tuple(denial.denied_action for denial in envelope.permission_denials)
        if denials:
            raise PermissionDeniedError(
                f"the harness denied {len(denials)} permission(s), so there is no report to trust: {', '.join(denials)}"
            )


class _TurnWatch:
    _TARGET_KEYS: ClassVar[tuple[str, ...]] = ("file_path", "path", "pattern", "command")

    def __init__(self, *, turns: TurnLog, slice_id: str) -> None:
        self._turns = turns
        self._slice_id = slice_id
        self._seen = 0

    def __call__(self, line: str) -> None:
        for tool_use in self._tool_uses_of(line):
            self._seen += 1
            self._turns.observe(
                HarnessTurn(
                    slice_id=self._slice_id,
                    step=Step.IMPLEMENT,
                    number=self._seen,
                    tool=tool_use.name,
                    target=self._target_of(tool_use.input),
                )
            )

    @classmethod
    def _tool_uses_of(cls, line: str) -> tuple[TranscriptToolUseBlock, ...]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return ()

        if not isinstance(data, dict) or data.get("type") != "assistant":
            return ()

        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            return ()

        blocks = (block for block in content if isinstance(block, dict) and block.get("type") == "tool_use")
        return tuple(tool_use for tool_use in (cls._legible(block) for block in blocks) if tool_use is not None)

    @staticmethod
    def _legible(block: dict[str, object]) -> TranscriptToolUseBlock | None:
        try:
            return TranscriptToolUseBlock.from_dict(block)
        except UnreadableConversationError:
            return None

    @classmethod
    def _target_of(cls, tool_input: dict[str, object]) -> str | None:
        for key in cls._TARGET_KEYS:
            value = tool_input.get(key)
            if isinstance(value, str):
                return value

        return None
