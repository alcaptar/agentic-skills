from __future__ import annotations

from slice_runner.infrastructure.understanding_brief import UnderstandingBrief


class TestWhatTheBriefPublishesAboutTheFloors:
    def test_no_heading_announces_a_section_of_floors_the_schema_can_no_longer_enforce(self) -> None:
        headings = [line for line in UnderstandingBrief.TEXT.splitlines() if line.startswith("##")]

        assert not any("minimo" in heading.lower() for heading in headings)

    def test_it_still_forbids_shrinking_the_report_to_pass_a_rejection(self) -> None:
        collapsed = " ".join(UnderstandingBrief.TEXT.split()).lower()

        assert "no lo reduzcas para que pase" in collapsed
