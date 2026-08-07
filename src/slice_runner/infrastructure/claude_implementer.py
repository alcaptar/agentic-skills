from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import PermissionDeniedError
from slice_runner.domain.implementation import Implementation
from slice_runner.domain.implementer import Implementer
from slice_runner.domain.step import Step
from slice_runner.infrastructure.call_trace import HarnessCall
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.implementer_invocation import ImplementerInvocation
from slice_runner.infrastructure.report_payload import ImplementationReportPayload

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.infrastructure.call_trace import CallTrace
    from slice_runner.infrastructure.process import Process


class ClaudeImplementer(Implementer):
    def __init__(self, *, process: Process, trace: CallTrace) -> None:
        self._process = process
        self._trace = trace

    def implement(self, assignment: Assignment) -> Implementation:
        invocation = ImplementerInvocation(assignment=assignment)
        output = self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd)
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
