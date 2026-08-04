from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.verifier import Verifier
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.verdict_payload import VerdictPayload

if TYPE_CHECKING:
    from slice_runner.domain.judge_prompt import JudgePrompt
    from slice_runner.domain.verdict import Verdict
    from slice_runner.infrastructure.process import Process


class ClaudeVerifier(Verifier):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def verify(self, prompt: JudgePrompt) -> Verdict:
        invocation = JudgeInvocation(prompt=prompt)
        output = self._process.run(invocation.argv, stdin=invocation.text)
        envelope = HarnessOutput.from_process(output)

        return VerdictPayload.from_dict(envelope.structured_output).to_domain()
