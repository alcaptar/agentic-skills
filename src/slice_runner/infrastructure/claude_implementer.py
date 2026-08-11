from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.domain.call_trace import HarnessCall
from slice_runner.domain.exceptions import PermissionDeniedError
from slice_runner.domain.implementation import Implementation
from slice_runner.domain.implementer import Implementer
from slice_runner.domain.step import Step
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.harness_turn_watch import HarnessTurnWatch
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.report_payload import ImplementationReportPayload

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.infrastructure.process import Process
    from slice_runner.infrastructure.tool_use_recorder import ToolUseRecorder
    from slice_runner.infrastructure.turn_log import TurnLog


class ClaudeImplementer(Implementer):
    def __init__(
        self,
        *,
        process: Process,
        trace: CallTrace,
        turns: TurnLog,
        spend_log: CallSpendLog,
        tool_uses: ToolUseRecorder,
    ) -> None:
        self._process = process
        self._trace = trace
        self._turns = turns
        self._spend_log = spend_log
        self._tool_uses = tool_uses

    def implement(self, assignment: Assignment) -> Implementation:
        invocation = ImplementerInvocation(assignment=assignment)
        watch = HarnessTurnWatch(turns=self._turns, slice_id=assignment.slice_id, step=Step.IMPLEMENT)
        output = self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd, on_line=watch)
        envelope = HarnessOutput.from_process(output)
        self._trace.record(
            HarnessCall(
                repo=assignment.repo,
                issue=assignment.issue,
                slice_id=assignment.slice_id,
                step=Step.IMPLEMENT,
                session=envelope.session_id,
            )
        )
        spend = envelope.to_domain()
        self._spend_log.record(
            HarnessCallSpend(repo=assignment.repo, issue=assignment.issue, session=envelope.session_id, spend=spend)
        )
        self._tool_uses.record_after(
            slice_id=assignment.slice_id, step=Step.IMPLEMENT, session=envelope.session_id, repo=assignment.worktree
        )
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
