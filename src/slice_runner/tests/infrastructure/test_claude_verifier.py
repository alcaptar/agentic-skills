from __future__ import annotations

import pytest

from slice_runner.domain.exceptions import InvalidVerdictError
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.step import Step
from slice_runner.infrastructure.claude_verifier import ClaudeVerifier
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.tests.doubles import RecordedProcess, RecordedTrace
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother, JudgeVerdictMother
from slice_runner.tests.mothers.verification_mother import JudgeMother, SliceUnderReviewMother

_JUDGE = JudgeMother.adversarial()


class TestTheVerdictOfARecordedCall:
    @pytest.mark.parametrize("recorded", HarnessEnvelopeMother.JUDGE_RECORDED)
    def test_the_envelope_of_both_real_calls_is_read_whole_from_structured_output(self, recorded: str) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded(recorded))

        verification = ClaudeVerifier(process=process, trace=RecordedTrace()).verify(
            JudgeMother.adversarial(), SliceUnderReviewMother.of_the_slice()
        )

        assert verification.verdict.ruling is Ruling.FAIL
        assert len(verification.verdict.findings) == 4

    def test_the_first_finding_of_the_recorded_call_arrives_whole(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        verification = ClaudeVerifier(process=process, trace=RecordedTrace()).verify(
            JudgeMother.adversarial(), SliceUnderReviewMother.of_the_slice()
        )

        first = verification.verdict.findings[0]
        assert (first.rule, first.path, first.line) == ("convenciones", "mod.py", 11)


class TestHowTheJudgeIsCalled:
    def test_the_prompt_travels_on_standard_input_and_not_in_the_argv(self) -> None:
        review = SliceUnderReviewMother.of_the_slice()
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        ClaudeVerifier(process=process, trace=RecordedTrace()).verify(_JUDGE, review)

        assert process.stdin == JudgeInvocation(judge=_JUDGE, review=review).text
        assert process.stdin not in process.argv

    def test_the_judge_is_invoked_exactly_once_because_a_retry_is_a_decision_of_whoever_orchestrates(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        ClaudeVerifier(process=process, trace=RecordedTrace()).verify(
            JudgeMother.adversarial(), SliceUnderReviewMother.of_the_slice()
        )

        assert process.calls == 1

    def test_the_judge_does_not_fix_a_model_so_it_keeps_the_best_one_available(self) -> None:
        argv = JudgeInvocation(judge=_JUDGE, review=SliceUnderReviewMother.of_the_slice()).argv

        assert "--model" not in argv


class TestWhatTheJudgeCallCost:
    def test_the_spend_of_the_call_comes_back_with_the_verdict_because_the_judge_is_not_free(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        verification = ClaudeVerifier(process=process, trace=RecordedTrace()).verify(
            _JUDGE, SliceUnderReviewMother.of_the_slice()
        )

        assert verification.spend == HarnessSpendMother.of_the_judge_call()


class TestWhereTheJudgeConversationCanBeFound:
    def test_the_session_the_call_ran_under_is_written_down_under_the_slice_and_the_step_it_served(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())
        trace = RecordedTrace()

        ClaudeVerifier(process=process, trace=trace).verify(_JUDGE, SliceUnderReviewMother.of_the_slice())

        assert [(call.slice_id, call.step, call.session) for call in trace.calls] == [
            (SliceUnderReviewMother.SLICE_ID, Step.VERIFY, HarnessEnvelopeMother.SESSION_OF_THE_JUDGE)
        ]

    def test_a_call_whose_verdict_is_discarded_is_traced_too_because_that_conversation_is_the_one_to_read(self) -> None:
        incoherent = JudgeVerdictMother.passing_with(JudgeVerdictMother.high_severity_finding())
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incoherent))
        trace = RecordedTrace()

        with pytest.raises(InvalidVerdictError):
            ClaudeVerifier(process=process, trace=trace).verify(_JUDGE, SliceUnderReviewMother.of_the_slice())

        assert [call.session for call in trace.calls] == [HarnessEnvelopeMother.SESSION_OF_THE_JUDGE]


class TestWhenTheJudgeAnswersSomethingIncoherent:
    def test_the_spend_survives_the_rejection_so_the_discarded_call_still_counts(self) -> None:
        incoherent = JudgeVerdictMother.passing_with(JudgeVerdictMother.high_severity_finding())
        process = RecordedProcess(HarnessEnvelopeMother.carrying(incoherent))

        with pytest.raises(InvalidVerdictError) as rejection:
            ClaudeVerifier(process=process, trace=RecordedTrace()).verify(_JUDGE, SliceUnderReviewMother.of_the_slice())

        assert rejection.value.spend == HarnessSpendMother.of_the_judge_call()


class TestWhatTheHarnessDeniedTheJudge:
    def test_a_denied_read_comes_back_with_the_verdict_so_nobody_has_to_reopen_the_envelope(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read())

        verification = ClaudeVerifier(process=process, trace=RecordedTrace()).verify(
            _JUDGE, SliceUnderReviewMother.of_the_slice()
        )

        assert verification.denied_reads == (f"Read {HarnessEnvelopeMother.DENIED_READ}",)

    def test_the_verdict_is_still_the_judges_because_a_denied_read_is_not_a_veto(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.denying_a_read(JudgeVerdictMother.passing()))

        verification = ClaudeVerifier(process=process, trace=RecordedTrace()).verify(
            _JUDGE, SliceUnderReviewMother.of_the_slice()
        )

        assert verification.verdict.ruling is Ruling.PASS

    def test_an_envelope_with_no_denials_leaves_nothing_to_warn_about(self) -> None:
        process = RecordedProcess(HarnessEnvelopeMother.recorded())

        verification = ClaudeVerifier(process=process, trace=RecordedTrace()).verify(
            _JUDGE, SliceUnderReviewMother.of_the_slice()
        )

        assert verification.denied_reads == ()
