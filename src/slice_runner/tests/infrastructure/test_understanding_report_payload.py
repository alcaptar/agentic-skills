from __future__ import annotations

import json

import pytest

from slice_runner.domain.exceptions import InvalidUnderstandingReportError
from slice_runner.infrastructure.understanding_report_payload import UnderstandingReportPayload
from slice_runner.tests.mothers.understanding_report_mother import UnderstandingReportMother


class TestTheSchemaTheHarnessReceives:
    def test_it_requires_the_summary_the_steps_and_the_sketch(self) -> None:
        assert UnderstandingReportPayload.json_schema()["required"] == ["summary", "steps", "sketch"]

    def test_it_travels_with_no_reference_left_because_only_the_flat_form_has_been_measured(self) -> None:
        emitted = json.dumps(UnderstandingReportPayload.json_schema())

        assert "$ref" not in emitted
        assert "$defs" not in emitted


class TestWhatTheHarnessIsAllowedToReturn:
    def test_a_full_report_is_accepted(self) -> None:
        report = UnderstandingReportPayload.from_dict(UnderstandingReportMother.valid())

        assert (report.summary, report.sketch) == (UnderstandingReportMother.SUMMARY, UnderstandingReportMother.SKETCH)
        assert [(step.description, step.reason) for step in report.steps] == [
            (UnderstandingReportMother.STEP_DESCRIPTION, UnderstandingReportMother.STEP_REASON)
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

    def test_eight_steps_are_accepted_because_that_is_the_cap_and_not_one_below_it(self) -> None:
        report = UnderstandingReportPayload.from_dict(UnderstandingReportMother.with_steps(8))

        assert len(report.steps) == 8
