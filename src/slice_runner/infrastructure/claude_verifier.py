from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.call_spend_log import HarnessCallSpend
from slice_runner.domain.call_trace import HarnessCall
from slice_runner.domain.step import Step
from slice_runner.domain.verification import Verification
from slice_runner.domain.verifier import Verifier
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.harness_turn_watch import HarnessTurnWatch
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.call_spend_log import CallSpendLog
    from slice_runner.domain.call_trace import CallTrace
    from slice_runner.domain.judge import Judge
    from slice_runner.domain.slice_under_review import SliceUnderReview
    from slice_runner.infrastructure.process import Process
    from slice_runner.infrastructure.tool_use_recorder import ToolUseRecorder
    from slice_runner.infrastructure.turn_log import TurnLog


class ClaudeVerifier(Verifier):
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

    def verify(self, judge: Judge, review: SliceUnderReview) -> Verification:
        invocation = JudgeInvocation(judge=judge, review=review)
        watch = HarnessTurnWatch(turns=self._turns, slice_id=review.slice_id, step=Step.VERIFY)
        output = self._process.run(invocation.argv, stdin=invocation.text, on_line=watch)
        envelope = HarnessOutput.from_process(output)
        self._trace.record(HarnessCall(slice_id=review.slice_id, step=Step.VERIFY, session=envelope.session_id))
        spend = envelope.to_domain()
        self._spend_log.record(HarnessCallSpend(session=envelope.session_id, spend=spend))
        self._tool_uses.record_after(
            slice_id=review.slice_id, step=Step.VERIFY, session=envelope.session_id, repo=review.repo
        )
        with envelope.measuring():
            verdict = VerdictPayload.from_dict(envelope.structured_output).to_domain()

        return Verification(
            verdict=verdict,
            spend=spend,
            denied_reads=tuple(denial.denied_action for denial in envelope.permission_denials),
        )
