from __future__ import annotations

import json
import re

import pytest

from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.understanding_brief import UnderstandingBrief
from slice_runner.infrastructure.understanding_report_payload import UnderstandingReportPayload
from slice_runner.tests.mothers.understanding_report_mother import UnderstandingReportMother


class TestTheSchemaTheHarnessReceives:
    def test_it_requires_the_summary_the_steps_and_the_sketch(self) -> None:
        assert UnderstandingReportPayload.json_schema()["required"] == ["summary", "steps", "sketch"]

    def test_it_travels_with_no_reference_left_because_only_the_flat_form_has_been_measured(self) -> None:
        emitted = json.dumps(UnderstandingReportPayload.json_schema())

        assert "$ref" not in emitted
        assert "$defs" not in emitted

    def test_it_carries_the_floors_so_the_harness_learns_them_from_the_schema_and_not_from_a_rejection(self) -> None:
        properties = UnderstandingReportPayload.json_schema()["properties"]

        assert isinstance(properties, dict)
        assert properties["summary"]["minLength"] > 0
        assert properties["steps"]["minItems"] > 0
        assert properties["sketch"]["minItems"] > 0

    def test_the_sketch_travels_as_pieces_so_the_harness_never_writes_the_code_block_itself(self) -> None:
        properties = UnderstandingReportPayload.json_schema()["properties"]

        assert isinstance(properties, dict)
        assert properties["sketch"]["type"] == "array"
        assert properties["sketch"]["items"]["required"] == ["signature", "does"]


class TestTheFloorsAreToldToTheHarnessAndNotOnlyEnforcedOnIt:
    @staticmethod
    def _announced_in_the_brief() -> dict[str, int]:
        section = UnderstandingBrief.TEXT.split("## Los minimos", maxsplit=1)[1]
        announced = {}
        for line in section.splitlines():
            named = re.match(r"- `(\w+)`: (.+)", line.strip())
            if named is None:
                continue
            announced[named.group(1)] = [int(number) for number in re.findall(r"\d+", named.group(2))]

        return {
            "summary": announced["summary"][0],
            "steps": announced["steps"][0],
            "step_description": announced["steps"][1],
            "sketch": announced["sketch"][0],
            "signature": announced["sketch"][1],
            "does": announced["sketch"][2],
        }

    def test_the_summary_floor_the_brief_announces_is_the_one_the_schema_enforces(self) -> None:
        properties = UnderstandingReportPayload.json_schema()["properties"]

        assert isinstance(properties, dict)
        assert properties["summary"]["minLength"] == self._announced_in_the_brief()["summary"]

    def test_the_step_floors_the_brief_announces_are_the_ones_the_schema_enforces(self) -> None:
        properties = UnderstandingReportPayload.json_schema()["properties"]
        announced = self._announced_in_the_brief()

        assert isinstance(properties, dict)
        assert properties["steps"]["minItems"] == announced["steps"]
        assert properties["steps"]["items"]["properties"]["description"]["minLength"] == announced["step_description"]

    def test_the_sketch_floors_the_brief_announces_are_the_ones_the_schema_enforces(self) -> None:
        properties = UnderstandingReportPayload.json_schema()["properties"]
        announced = self._announced_in_the_brief()

        assert isinstance(properties, dict)
        assert properties["sketch"]["minItems"] == announced["sketch"]
        assert properties["sketch"]["items"]["properties"]["signature"]["minLength"] == announced["signature"]
        assert properties["sketch"]["items"]["properties"]["does"]["minLength"] == announced["does"]


class TestWhatTheHarnessIsAllowedToReturn:
    def test_a_full_report_is_accepted(self) -> None:
        report = UnderstandingReportPayload.from_dict(UnderstandingReportMother.valid())

        assert report.summary == UnderstandingReportMother.SUMMARY
        assert [(step.description, step.reason) for step in report.steps] == [
            (UnderstandingReportMother.STEP_DESCRIPTION, UnderstandingReportMother.STEP_REASON),
            (UnderstandingReportMother.SECOND_STEP_DESCRIPTION, UnderstandingReportMother.SECOND_STEP_REASON),
        ]
        assert [(piece.signature, piece.does) for piece in report.sketch] == [
            (UnderstandingReportMother.SIGNATURE, UnderstandingReportMother.DOES)
        ]

    def test_a_report_missing_the_sketch_is_rejected_instead_of_passing_through_as_free_text(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="sketch"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.without("sketch"))

    def test_a_report_missing_the_summary_is_rejected(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="summary"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.without("summary"))

    def test_a_report_missing_the_steps_is_rejected(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="steps"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.without("steps"))

    def test_a_step_missing_its_reason_is_rejected_instead_of_passing_through_as_prose_in_the_description(
        self,
    ) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="reason"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_a_step_missing_its_reason())

    def test_a_piece_missing_what_it_does_is_rejected_because_a_signature_alone_shows_no_shape(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="does"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_a_piece_missing_what_it_does())

    def test_eight_steps_are_accepted_because_the_floor_caps_nothing_above_it(self) -> None:
        report = UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_steps(8))

        assert len(report.steps) == 8


class TestWhatTheFloorsKeepOut:
    def test_the_report_that_the_harness_degraded_to_placeholders_is_rejected_instead_of_published(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.filled_with_placeholders())

    def test_a_single_step_is_rejected_because_a_plan_of_one_step_is_not_a_plan(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="steps"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_steps(1))

    def test_an_empty_sketch_is_rejected_because_the_shape_is_what_the_gate_exists_to_show(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="sketch"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_pieces(0))

    def test_a_summary_of_a_few_words_is_rejected_because_it_cannot_be_told_from_not_having_understood(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="summary"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.valid() | {"summary": "lo he entendido"})
