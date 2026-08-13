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
    from slice_runner.domain.source_reader import SourceReader
    from slice_runner.infrastructure.harness_telemetry import HarnessTelemetry
    from slice_runner.infrastructure.process import Process


class ClaudeImplementer(Implementer):
    def __init__(self, *, process: Process, telemetry: HarnessTelemetry, reader: SourceReader) -> None:
        self._process = process
        self._telemetry = telemetry
        self._reader = reader

    def implement(self, assignment: Assignment) -> Implementation:
        invocation = ImplementerInvocation(assignment=assignment, reader=self._reader)
        watch = HarnessTurnWatch(turns=self._telemetry.turns, slice_id=assignment.slice_id, step=Step.IMPLEMENT)
        output = self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd, on_line=watch)
        envelope = HarnessOutput.from_process(output)
        self._telemetry.trace.record(
            HarnessCall(
                repo=assignment.repo,
                issue=assignment.issue,
                slice_id=assignment.slice_id,
                step=Step.IMPLEMENT,
                session=envelope.session_id,
            )
        )
        spend = envelope.to_domain()
        self._telemetry.spend_log.record(
            HarnessCallSpend(repo=assignment.repo, issue=assignment.issue, session=envelope.session_id, spend=spend)
        )
        self._telemetry.tool_uses.record_after(
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
