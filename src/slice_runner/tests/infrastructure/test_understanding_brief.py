from __future__ import annotations

import re

from slice_runner.infrastructure.understanding_brief import UnderstandingBrief

_A_STATED_FLOOR = re.compile(r"al menos\s+\d")


class TestWhatTheBriefPublishesAboutTheFloors:
    def test_no_heading_announces_a_section_of_floors_the_schema_can_no_longer_enforce(self) -> None:
        headings = [line for line in UnderstandingBrief.TEXT.splitlines() if line.startswith("##")]

        assert not any("minimo" in heading.lower() for heading in headings)

    def test_no_figure_in_the_body_tells_the_agent_how_little_is_enough_whatever_the_heading_says(self) -> None:
        assert not _A_STATED_FLOOR.search(" ".join(UnderstandingBrief.TEXT.split()).lower())

    def test_it_still_forbids_shrinking_the_report_to_pass_a_rejection(self) -> None:
        collapsed = " ".join(UnderstandingBrief.TEXT.split()).lower()

        assert "no lo reduzcas para que pase" in collapsed


class TestWhereTheFieldsAreSpecified:
    def test_the_brief_does_not_respec_the_fields_the_schema_already_describes(self) -> None:
        collapsed = " ".join(UnderstandingBrief.TEXT.split())

        assert not any(field in collapsed for field in ("`signature`", "`does`", "`reason`"))

    def test_it_still_says_both_fields_are_mandatory_because_emitting_only_one_is_the_failure_measured(self) -> None:
        collapsed = " ".join(UnderstandingBrief.TEXT.split()).lower()

        assert "los dos campos son obligatorios" in collapsed
