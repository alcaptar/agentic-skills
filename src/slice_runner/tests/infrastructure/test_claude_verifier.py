from __future__ import annotations

import pytest

from slice_runner.domain.ruling import Ruling
from slice_runner.infrastructure.claude_verifier import ClaudeVerifier
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.tests.doubles import RecordedProcess
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother
from slice_runner.tests.mothers.verification_mother import JudgePromptMother


class TestTheVerdictOfARecordedCall:
    @pytest.mark.parametrize("recorded", HarnessEnvelopeMother.RECORDED)
    def test_the_envelope_of_both_real_calls_is_read_whole_from_structured_output(self, recorded: str) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(recorded))

        verdict = ClaudeVerifier(process=process).verify(JudgePromptMother.for_the_slice())

        assert verdict.ruling is Ruling.FAIL
        assert len(verdict.findings) == 4

    def test_the_first_finding_of_the_recorded_call_arrives_whole(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        verdict = ClaudeVerifier(process=process).verify(JudgePromptMother.for_the_slice())

        first = verdict.findings[0]
        assert (first.rule, first.path, first.line) == ("convenciones", "mod.py", 11)


class TestHowTheJudgeIsCalled:
    def test_the_prompt_travels_on_standard_input_and_not_in_the_argv(self) -> None:
        prompt = JudgePromptMother.for_the_slice()
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        ClaudeVerifier(process=process).verify(prompt)

        assert process.stdin == JudgeInvocation(prompt=prompt).text
        assert process.stdin not in process.argv

    def test_the_judge_is_invoked_exactly_once_because_a_retry_is_a_decision_of_whoever_orchestrates(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        ClaudeVerifier(process=process).verify(JudgePromptMother.for_the_slice())

        assert process.calls == 1
