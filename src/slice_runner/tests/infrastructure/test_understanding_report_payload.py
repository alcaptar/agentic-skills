from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.understanding_report_payload import UnderstandingReportPayload
from slice_runner.tests.mothers.understanding_report_mother import UnderstandingReportMother


class TestTheSchemaTheHarnessReceives:
    def test_it_requires_the_summary_and_the_plan(self) -> None:
        assert UnderstandingReportPayload.json_schema()["required"] == ["summary", "plan"]

    def test_it_travels_with_no_reference_left_because_only_the_flat_form_has_been_measured(self) -> None:
        emitted = json.dumps(UnderstandingReportPayload.json_schema())

        assert "$ref" not in emitted
        assert "$defs" not in emitted

    def test_the_plan_travels_as_pieces_so_the_harness_never_writes_the_code_block_itself(self) -> None:
        properties = UnderstandingReportPayload.json_schema()["properties"]

        assert isinstance(properties, dict)
        assert properties["plan"]["type"] == "array"
        assert properties["plan"]["items"]["required"] == ["signature", "does", "reason"]

    def test_no_field_declares_a_floor_the_structured_output_api_cannot_enforce(self) -> None:
        emitted = json.dumps(UnderstandingReportPayload.json_schema())

        assert "minLength" not in emitted
        assert "minItems" not in emitted


class TestWhatTheSchemaSaysEachFieldIsFor:
    @staticmethod
    def _fields() -> list[dict[str, object]]:
        properties = UnderstandingReportPayload.json_schema()["properties"]

        assert isinstance(properties, dict)

        return [properties["summary"], properties["plan"], *properties["plan"]["items"]["properties"].values()]

    def test_every_field_says_what_goes_in_it_because_the_schema_is_what_the_agent_reads_when_it_emits(self) -> None:
        assert all(field.get("description") for field in self._fields())

    def test_the_summary_is_told_the_plan_does_not_go_in_it_because_that_is_the_failure_measured(self) -> None:
        properties = UnderstandingReportPayload.json_schema()["properties"]

        assert isinstance(properties, dict)
        assert "no el plan" in properties["summary"]["description"]


class TestWhatTheHarnessIsAllowedToReturn:
    def test_a_full_report_is_accepted(self) -> None:
        report = UnderstandingReportPayload.from_dict(UnderstandingReportMother.valid())

        assert report.summary == UnderstandingReportMother.SUMMARY
        assert [(piece.signature, piece.does, piece.reason) for piece in report.plan] == [
            (UnderstandingReportMother.SIGNATURE, UnderstandingReportMother.DOES, UnderstandingReportMother.REASON),
            (
                UnderstandingReportMother.SECOND_SIGNATURE,
                UnderstandingReportMother.SECOND_DOES,
                UnderstandingReportMother.SECOND_REASON,
            ),
        ]

    def test_a_report_missing_the_plan_is_rejected_instead_of_passing_through_as_free_text(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="plan"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.without("plan"))

    def test_a_report_missing_the_summary_is_rejected(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="summary"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.without("summary"))

    def test_a_piece_missing_its_signature_is_rejected(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="signature"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_a_piece_missing_its_signature())

    def test_a_piece_missing_what_it_does_is_rejected_because_a_signature_alone_shows_no_shape(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="does"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_a_piece_missing_what_it_does())

    def test_a_piece_missing_its_reason_is_rejected_instead_of_passing_through_as_prose_in_does(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="reason"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_a_piece_missing_its_reason())

    def test_eight_pieces_are_accepted_because_nothing_caps_the_plan_from_above(self) -> None:
        report = UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_pieces(8))

        assert len(report.plan) == 8
