from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import InvalidResolutionReportError
from slice_runner.infrastructure.conflict_resolution_report_payload import ConflictResolutionReportPayload
from slice_runner.tests.mothers.resolution_report_mother import ResolutionReportMother


class TestTheSchemaTheHarnessReceives:
    def test_it_asks_for_a_single_field_because_a_second_one_is_a_boundary_the_harness_loses(self) -> None:
        schema = ConflictResolutionReportPayload.json_schema()
        properties = schema["properties"]

        assert isinstance(properties, dict)
        assert list(properties) == ["summary"]
        assert schema["required"] == ["summary"]

    def test_it_travels_with_no_reference_left_because_only_the_flat_form_has_been_measured(self) -> None:
        emitted = json.dumps(ConflictResolutionReportPayload.json_schema())

        assert "$ref" not in emitted
        assert "$defs" not in emitted

    def test_the_only_field_says_what_goes_in_it_because_the_schema_is_what_the_agent_reads_when_it_emits(
        self,
    ) -> None:
        properties = ConflictResolutionReportPayload.json_schema()["properties"]

        assert isinstance(properties, dict)
        assert properties["summary"]["description"]


class TestWhatTheHarnessIsAllowedToReturn:
    def test_a_full_report_is_accepted_whole(self) -> None:
        report = ConflictResolutionReportPayload.from_dict(ResolutionReportMother.valid())

        assert report.summary == ResolutionReportMother.SUMMARY

    def test_a_report_missing_its_only_field_is_rejected(self) -> None:
        with pytest.raises(InvalidResolutionReportError, match="summary"):
            ConflictResolutionReportPayload.from_dict(ResolutionReportMother.without("summary"))

    def test_a_field_the_contract_never_declared_is_rejected_instead_of_being_ignored(self) -> None:
        with pytest.raises(InvalidResolutionReportError, match="paths"):
            ConflictResolutionReportPayload.from_dict(ResolutionReportMother.with_an_unknown_field())
