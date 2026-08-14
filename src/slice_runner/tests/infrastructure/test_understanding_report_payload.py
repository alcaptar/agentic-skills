from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.understanding_report_payload import UnderstandingReportPayload
from slice_runner.tests.mothers.understanding_report_mother import UnderstandingReportMother


class TestTheSchemaTheHarnessReceives:
    def test_it_asks_for_a_single_field_because_a_second_one_is_a_boundary_the_harness_loses(self) -> None:
        schema = UnderstandingReportPayload.json_schema()
        properties = schema["properties"]

        assert isinstance(properties, dict)
        assert list(properties) == ["report"]
        assert schema["required"] == ["report"]

    def test_it_travels_with_no_reference_left_because_only_the_flat_form_has_been_measured(self) -> None:
        emitted = json.dumps(UnderstandingReportPayload.json_schema())

        assert "$ref" not in emitted
        assert "$defs" not in emitted

    def test_no_field_declares_a_floor_the_structured_output_api_cannot_enforce(self) -> None:
        emitted = json.dumps(UnderstandingReportPayload.json_schema())

        assert "minLength" not in emitted
        assert "minItems" not in emitted

    def test_the_only_field_says_what_goes_in_it_because_the_schema_is_what_the_agent_reads_when_it_emits(self) -> None:
        properties = UnderstandingReportPayload.json_schema()["properties"]

        assert isinstance(properties, dict)
        assert properties["report"]["description"]


class TestWhatTheHarnessIsAllowedToReturn:
    def test_a_full_report_is_accepted_whole_instead_of_being_split_into_fields(self) -> None:
        report = UnderstandingReportPayload.from_dict(UnderstandingReportMother.valid())

        assert report.report == UnderstandingReportMother.REPORT

    def test_a_report_missing_its_only_field_is_rejected(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="report"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.without("report"))

    def test_a_field_the_contract_never_declared_is_rejected_instead_of_being_ignored(self) -> None:
        with pytest.raises(InvalidUnderstandingReportError, match="plan"):
            UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_an_unknown_field())
