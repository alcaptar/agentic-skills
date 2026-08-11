from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import InvalidHarnessOutputError
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother


class TestTheEnvelopeWeKnow:
    @pytest.mark.parametrize("recorded", HarnessEnvelopeMother.ALL_RECORDED)
    def test_every_recorded_call_validates_whole_so_the_declared_keys_are_the_real_ones(self, recorded: str) -> None:
        envelope = HarnessOutput.from_dict(HarnessEnvelopeMother.recorded(recorded))

        assert envelope.is_error is False
        assert envelope.structured_output

    def test_a_key_we_do_not_know_is_rejected_instead_of_ignored(self) -> None:
        with pytest.raises(InvalidHarnessOutputError, match="campo_nuevo_del_harness"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.plus(campo_nuevo_del_harness=1))

    def test_a_text_that_looks_like_a_boolean_is_not_taken_as_one(self) -> None:
        with pytest.raises(InvalidHarnessOutputError, match=r"`is_error`.*valid boolean"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.plus(is_error="no"))

    def test_one_without_structured_output_is_rejected_instead_of_falling_back_to_result(self) -> None:
        with pytest.raises(InvalidHarnessOutputError, match="structured_output"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.without("structured_output"))

    def test_one_without_structured_output_that_ran_out_of_turns_says_so_in_the_rejection(self) -> None:
        envelope = HarnessEnvelopeMother.without("structured_output") | {"subtype": "error_max_turns"}

        with pytest.raises(InvalidHarnessOutputError, match="error_max_turns"):
            HarnessOutput.from_dict(envelope)

    def test_one_without_structured_output_and_without_any_cause_field_does_not_invent_one(self) -> None:
        cause_fields = ("is_error", "subtype", "stop_reason", "terminal_reason")
        envelope = {
            key: value
            for key, value in HarnessEnvelopeMother.without("structured_output").items()
            if key not in cause_fields
        }

        with pytest.raises(InvalidHarnessOutputError) as rejection:
            HarnessOutput.from_dict(envelope)

        assert "session ended" not in str(rejection.value)


class TestWhatTheHarnessMeasured:
    @pytest.mark.parametrize("recorded", HarnessEnvelopeMother.ALL_RECORDED)
    def test_every_recorded_call_brings_the_three_numbers_the_durable_log_records(self, recorded: str) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.recorded(recorded)).to_domain()

        assert spend.measured
        assert (spend.cost_usd > 0, spend.turns > 0, spend.duration_ms > 0) == (True, True, True)

    def test_the_recorded_call_of_the_implementer_arrives_with_its_own_figures(self) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.recorded("implementer-two-paths")).to_domain()

        assert (spend.cost_usd, spend.turns, spend.duration_ms) == (0.3433209, 9, 36315)

    def test_one_call_is_one_call_so_a_sum_of_two_can_be_told_apart_from_a_single_one(self) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.recorded()).to_domain()

        assert spend.calls == 1

    def test_an_envelope_without_the_duration_is_rejected_instead_of_recorded_as_zero_time(self) -> None:
        with pytest.raises(InvalidHarnessOutputError, match="duration_ms"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.without("duration_ms"))

    def test_a_duration_that_is_not_a_number_is_rejected_because_the_log_takes_no_estimates(self) -> None:
        with pytest.raises(InvalidHarnessOutputError, match="duration_ms"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.plus(duration_ms="a while"))

    def test_the_judge_call_arrives_with_the_model_the_harness_declares_and_its_cache_reads(self) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.recorded("full-recipe")).to_domain()

        assert spend.models == ("claude-haiku-4-5-20251001",)
        assert spend.cache_read_tokens == 15510

    def test_the_implementer_call_arrives_with_its_own_model_and_cache_reads(self) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.recorded("implementer-two-paths")).to_domain()

        assert spend.models == ("claude-sonnet-5",)
        assert spend.cache_read_tokens == 241303

    def test_an_envelope_without_model_usage_arrives_with_no_model_and_zero_cache_reads(self) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.without("modelUsage")).to_domain()

        assert spend.models == ()
        assert spend.cache_read_tokens == 0

    def test_the_recorded_call_of_the_judge_arrives_with_its_tokens_and_its_latencies(self) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.recorded("full-recipe")).to_domain()

        assert (
            spend.input_tokens,
            spend.output_tokens,
            spend.cache_creation_tokens,
            spend.ttft_ms,
            spend.duration_api_ms,
        ) == (17, 3443, 16547, 5384, 28905)

    def test_an_envelope_without_model_usage_arrives_with_zero_for_every_new_token_field_too(self) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.without("modelUsage")).to_domain()

        assert (spend.input_tokens, spend.output_tokens, spend.cache_creation_tokens) == (0, 0, 0)

    def test_an_envelope_without_the_time_to_first_token_arrives_with_zero_instead_of_breaking(self) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.without("ttft_ms")).to_domain()

        assert spend.ttft_ms == 0

    def test_an_envelope_without_the_api_call_duration_arrives_with_zero_instead_of_breaking(self) -> None:
        spend = HarnessOutput.from_dict(HarnessEnvelopeMother.without("duration_api_ms")).to_domain()

        assert spend.duration_api_ms == 0

    def test_a_model_usage_entry_missing_one_of_the_new_token_fields_still_parses_with_zero_for_it(self) -> None:
        recorded = HarnessEnvelopeMother.recorded("full-recipe")
        model_usage = recorded["modelUsage"]
        assert isinstance(model_usage, dict)
        model_id, entry = next(iter(model_usage.items()))
        assert isinstance(entry, dict)
        incomplete = {key: value for key, value in entry.items() if key != "outputTokens"}
        broken = recorded | {"modelUsage": {model_id: incomplete}}

        spend = HarnessOutput.from_dict(broken).to_domain()

        assert spend.output_tokens == 0

    def test_a_model_usage_entry_with_a_key_we_do_not_know_is_rejected_instead_of_ignored(self) -> None:
        recorded = HarnessEnvelopeMother.recorded("full-recipe")
        model_usage = recorded["modelUsage"]
        assert isinstance(model_usage, dict)
        model_id, entry = next(iter(model_usage.items()))
        assert isinstance(entry, dict)
        broken = recorded | {"modelUsage": {model_id: entry | {"campo_nuevo_del_harness": 1}}}

        with pytest.raises(InvalidHarnessOutputError, match="campo_nuevo_del_harness"):
            HarnessOutput.from_dict(broken)


class TestTheSessionEveryCallRunsUnder:
    def test_an_envelope_without_it_is_rejected_because_a_conversation_nobody_can_find_again_is_no_trace_at_all(
        self,
    ) -> None:
        with pytest.raises(InvalidHarnessOutputError, match="session_id"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.without("session_id"))

    def test_a_session_that_is_not_text_is_rejected_because_a_number_cannot_name_a_conversation(self) -> None:
        with pytest.raises(InvalidHarnessOutputError, match="session_id"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.plus(session_id=17))


class TestAStreamedEnvelope:
    def test_the_spend_extracts_the_same_as_the_single_object_envelope(self) -> None:
        spend = HarnessOutput.from_process(self._streamed()).to_domain()

        assert (spend.cost_usd, spend.turns, spend.duration_ms) == (0.0180821, 3, 4236)

    def test_the_structured_output_is_the_one_carried_by_the_final_line_and_not_a_turn_in_between(self) -> None:
        envelope = HarnessOutput.from_process(self._streamed())

        assert envelope.structured_output == {"paths": [{"path": "hello.py", "kind": "production"}], "left_out": []}

    def test_permission_denials_still_extract_empty_when_none_of_the_turns_were_denied(self) -> None:
        envelope = HarnessOutput.from_process(self._streamed())

        assert envelope.permission_denials == ()

    def test_the_lines_that_are_not_the_final_result_do_not_have_to_validate_at_all(self) -> None:
        stdout = HarnessEnvelopeMother.streamed()
        turns = "\n".join(line for line in stdout.splitlines() if json.loads(line).get("type") == "assistant")

        assert turns
        assert "structured_output" not in turns

    @staticmethod
    def _streamed() -> ProcessOutput:
        return ProcessOutput(code=0, stdout=HarnessEnvelopeMother.streamed(), stderr="")


class TestWhatTheProcessLeftBehind:
    def test_a_call_the_harness_declares_failed_is_rejected(self) -> None:
        output = self._carrying(HarnessEnvelopeMother.plus(is_error=True))

        with pytest.raises(InvalidHarnessOutputError, match="marked the call as failed"):
            HarnessOutput.from_process(output)

    def test_a_failed_call_still_reports_what_it_spent_because_it_was_paid_for_all_the_same(self) -> None:
        output = self._carrying(HarnessEnvelopeMother.plus(is_error=True))

        with pytest.raises(InvalidHarnessOutputError) as rejection:
            HarnessOutput.from_process(output)

        assert rejection.value.spend == HarnessSpendMother.of_the_judge_call()

    def test_output_that_never_parsed_carries_no_spend_because_nothing_got_measured(self) -> None:
        output = ProcessOutput(code=1, stdout="", stderr="error: unknown option '--tools'")

        with pytest.raises(InvalidHarnessOutputError) as rejection:
            HarnessOutput.from_process(output)

        assert rejection.value.spend is None

    def test_output_that_is_not_json_is_rejected_with_what_the_process_left_on_stderr(self) -> None:
        output = ProcessOutput(code=1, stdout="", stderr="error: unknown option '--tools'")

        with pytest.raises(InvalidHarnessOutputError, match="unknown option"):
            HarnessOutput.from_process(output)

    def test_output_that_is_json_but_not_an_object_is_rejected(self) -> None:
        output = ProcessOutput(code=0, stdout="[]", stderr="")

        with pytest.raises(InvalidHarnessOutputError, match="has to be an object"):
            HarnessOutput.from_process(output)

    def test_a_process_that_said_nothing_at_all_is_reported_as_that_and_not_as_a_parse_error(self) -> None:
        output = ProcessOutput(code=137, stdout="", stderr="")

        with pytest.raises(InvalidHarnessOutputError, match=r"code 137.*\(no output\)"):
            HarnessOutput.from_process(output)

    @staticmethod
    def _carrying(envelope: dict[str, object]) -> ProcessOutput:
        return ProcessOutput(code=0, stdout=json.dumps(envelope), stderr="")
