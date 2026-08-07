from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import PermissionDeniedError
from slice_runner.domain.implementation import Implementation
from slice_runner.domain.implementer import Implementer
from slice_runner.domain.step import Step
from slice_runner.infrastructure.call_trace import HarnessCall
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.report_payload import ImplementationReportPayload
from slice_runner.infrastructure.turn_log import HarnessTurn

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.infrastructure.call_trace import CallTrace
    from slice_runner.infrastructure.process import Process
    from slice_runner.infrastructure.turn_log import TurnLog


class ClaudeImplementer(Implementer):
    def __init__(self, *, process: Process, trace: CallTrace, turns: TurnLog) -> None:
        self._process = process
        self._trace = trace
        self._turns = turns

    def implement(self, assignment: Assignment) -> Implementation:
        invocation = ImplementerInvocation(assignment=assignment)
        watch = _TurnWatch(turns=self._turns, slice_id=assignment.slice_id)
        output = self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd, on_line=watch)
        envelope = HarnessOutput.from_process(output)
        self._trace.record(HarnessCall(slice_id=assignment.slice_id, step=Step.IMPLEMENT, session=envelope.session_id))
        with envelope.measuring():
            self._reject_denials(envelope)
            report = ImplementationReportPayload.from_dict(envelope.structured_output)

        return Implementation(paths=report.to_domain(), left_out=tuple(report.left_out), spend=envelope.to_domain())

    @staticmethod
    def _reject_denials(envelope: HarnessOutput) -> None:
        denials = tuple(denial.denied_action for denial in envelope.permission_denials)
        if denials:
            raise PermissionDeniedError(
                f"the harness denied {len(denials)} permission(s), so there is no report to trust: {', '.join(denials)}"
            )


class _TurnWatch:
    def __init__(self, *, turns: TurnLog, slice_id: str) -> None:
        self._turns = turns
        self._slice_id = slice_id
        self._seen = 0

    def __call__(self, line: str) -> None:
        if not self._is_a_turn(line):
            return

        self._seen += 1
        self._turns.observe(HarnessTurn(slice_id=self._slice_id, step=Step.IMPLEMENT, number=self._seen))

    @staticmethod
    def _is_a_turn(line: str) -> bool:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return False

        return isinstance(data, dict) and data.get("type") == "assistant"
