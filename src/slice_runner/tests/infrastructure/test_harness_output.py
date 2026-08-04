from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import InvalidVerdictError
from slice_runner.infrastructure.harness_output import HarnessOutput
from slice_runner.infrastructure.process import ProcessOutput
from slice_runner.tests.mothers.judge_output_mother import HarnessEnvelopeMother


class TestTheEnvelopeWeKnow:
    @pytest.mark.parametrize("recorded", HarnessEnvelopeMother.RECORDED)
    def test_every_recorded_call_validates_whole_so_the_declared_keys_are_the_real_ones(self, recorded: str) -> None:
        envelope = HarnessOutput.from_dict(HarnessEnvelopeMother.recorded(recorded))

        assert envelope.is_error is False
        assert envelope.structured_output

    def test_a_key_we_do_not_know_is_rejected_instead_of_ignored(self) -> None:
        with pytest.raises(InvalidVerdictError, match="campo_nuevo_del_harness"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.plus(campo_nuevo_del_harness=1))

    def test_a_text_that_looks_like_a_boolean_is_not_taken_as_one(self) -> None:
        with pytest.raises(InvalidVerdictError, match=r"`is_error`.*valid boolean"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.plus(is_error="no"))

    def test_one_without_structured_output_is_rejected_instead_of_falling_back_to_result(self) -> None:
        with pytest.raises(InvalidVerdictError, match="structured_output"):
            HarnessOutput.from_dict(HarnessEnvelopeMother.without("structured_output"))


class TestWhatTheProcessLeftBehind:
    def test_a_call_the_harness_declares_failed_is_rejected(self) -> None:
        output = self._carrying(HarnessEnvelopeMother.plus(is_error=True))

        with pytest.raises(InvalidVerdictError, match="marked the call as failed"):
            HarnessOutput.from_process(output)

    def test_output_that_is_not_json_is_rejected_with_what_the_process_left_on_stderr(self) -> None:
        output = ProcessOutput(code=1, stdout="", stderr="error: unknown option '--tools'")

        with pytest.raises(InvalidVerdictError, match="unknown option"):
            HarnessOutput.from_process(output)

    def test_output_that_is_json_but_not_an_object_is_rejected(self) -> None:
        output = ProcessOutput(code=0, stdout="[]", stderr="")

        with pytest.raises(InvalidVerdictError, match="has to be an object"):
            HarnessOutput.from_process(output)

    def test_a_process_that_said_nothing_at_all_is_reported_as_that_and_not_as_a_parse_error(self) -> None:
        output = ProcessOutput(code=137, stdout="", stderr="")

        with pytest.raises(InvalidVerdictError, match=r"code 137.*\(no output\)"):
            HarnessOutput.from_process(output)

    @staticmethod
    def _carrying(envelope: dict[str, object]) -> ProcessOutput:
        return ProcessOutput(code=0, stdout=json.dumps(envelope), stderr="")
