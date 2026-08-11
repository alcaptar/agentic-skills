from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from slice_runner.domain.assignment import Assignment
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother


class AssignmentMother:
    REPO: ClassVar[str] = "/repos/agentic-skills"
    UNDERSTANDING: ClassVar[str] = (
        "El precheck de subissue cerrada se llama `SUBISSUE_ALREADY_CLOSED` y corta antes de tocar la rama."
    )
    RETRY_INSTRUCTION: ClassVar[str] = "el control ya esta arreglado a mano"

    @classmethod
    def of_the_first_round(cls) -> Assignment:
        subissue = SubIssueMother.pending()
        parent = ParentIssueMother.with_sources_and_controls()

        return Assignment(
            issue=subissue.number,
            slice_id=subissue.slice_id,
            repo=cls.REPO,
            intention=subissue.intention,
            criteria=subissue.criteria,
            signal=subissue.signal,
            sources=parent.sources,
            controls=parent.controls,
        )

    @classmethod
    def of_a_second_round(cls) -> Assignment:
        return replace(cls.of_the_first_round(), findings=(FindingMother.with_line(),))

    @classmethod
    def of_a_round_after_red_controls(cls) -> Assignment:
        return replace(cls.of_the_first_round(), control_logs=(ControlOutcomeMother.LOG,))

    @classmethod
    def of_a_round_after_a_dirty_index(cls) -> Assignment:
        return replace(
            cls.of_the_first_round(),
            hygiene_refusal="the staged index is not what the implementer reported: src/leftover.py (not-declared)",
        )

    @classmethod
    def of_a_repo_exempt_from_controls(cls) -> Assignment:
        return replace(cls.of_the_first_round(), controls=ParentIssueMother.with_exempt_controls().controls)

    @classmethod
    def of_the_first_round_with_an_agreed_understanding(cls) -> Assignment:
        return replace(cls.of_the_first_round(), understanding=cls.UNDERSTANDING)

    @classmethod
    def of_a_round_after_reopening(cls) -> Assignment:
        return replace(cls.of_the_first_round(), retry_instruction=cls.RETRY_INSTRUCTION)
