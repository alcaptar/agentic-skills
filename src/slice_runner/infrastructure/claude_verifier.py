from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.step import Step
from slice_runner.domain.verification import Verification
from slice_runner.domain.verifier import Verifier
from slice_runner.infrastructure.call_trace import HarnessCall
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.slice_under_review import SliceUnderReview
    from slice_runner.infrastructure.call_trace import CallTrace
    from slice_runner.infrastructure.process import Process


class ClaudeVerifier(Verifier):
    def __init__(self, *, process: Process, trace: CallTrace) -> None:
        self._process = process
        self._trace = trace

    def verify(self, judge: Judge, review: SliceUnderReview) -> Verification:
        invocation = JudgeInvocation(judge=judge, review=review)
        output = self._process.run(invocation.argv, stdin=invocation.text)
        envelope = HarnessOutput.from_process(output)
        self._trace.record(HarnessCall(slice_id=review.slice_id, step=Step.VERIFY, session=envelope.session_id))
        with envelope.measuring():
            verdict = VerdictPayload.from_dict(envelope.structured_output).to_domain()

        return Verification(
            verdict=verdict,
            spend=envelope.to_domain(),
            denied_reads=tuple(denial.denied_action for denial in envelope.permission_denials),
        )
