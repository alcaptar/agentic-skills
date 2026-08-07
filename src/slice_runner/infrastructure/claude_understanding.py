from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.call_trace import HarnessCall
from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.domain.step import Step
from slice_runner.domain.understanding import Understanding
from slice_runner.domain.understanding_writer import UnderstandingWriter
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.understanding_invocation import UnderstandingInvocation
from slice_runner.infrastructure.understanding_report_payload import UnderstandingReportPayload

if TYPE_CHECKING:
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.domain.parent_issue import ParentIssue
    from slice_runner.domain.sub_issue import SubIssue
    from slice_runner.infrastructure.process import Process


class ClaudeUnderstanding(UnderstandingWriter):
    def __init__(self, *, process: Process, trace: CallTrace) -> None:
        self._process = process
        self._trace = trace

    def write(self, *, subissue: SubIssue, parent: ParentIssue, repo: str, worktree: str) -> Understanding:
        invocation = UnderstandingInvocation(subissue=subissue, parent=parent, repo=repo, worktree=worktree)
        output = self._process.run(invocation.argv, stdin=invocation.text, cwd=invocation.cwd)
        envelope = HarnessOutput.from_process(output)
        self._trace.record(HarnessCall(slice_id=subissue.slice_id, step=Step.UNDERSTAND, session=envelope.session_id))
        with envelope.measuring():
            text = self._usable_text(envelope)

        return Understanding(text=text, spend=envelope.to_domain())

    @staticmethod
    def _usable_text(envelope: HarnessOutput) -> str:
        report = UnderstandingReportPayload.from_dict(envelope.structured_output)
        text = report.understanding.strip()
        if not text:
            raise InvalidUnderstandingReportError("the harness returned only blank text as its understanding")

        return text
