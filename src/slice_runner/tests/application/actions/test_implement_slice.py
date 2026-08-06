from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.implement_slice import ImplementSlice, ImplementSliceParams
from slice_runner.domain.implementer import Implementer
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.finding import Finding

_WORKTREE = "/repos/agentic-skills"


class TestImplementSlice:
    @pytest.fixture
    def implementer(self) -> Mock:
        implementer: Mock = create_autospec(Implementer, spec_set=True, instance=True)
        implementer.implement.return_value = ImplementationMother.of_two_paths()
        return implementer

    @pytest.fixture
    def action(self, implementer: Mock) -> ImplementSlice:
        return ImplementSlice(implementer=implementer)

    @staticmethod
    def _params(*findings: Finding) -> ImplementSliceParams:
        return ImplementSliceParams(
            worktree=_WORKTREE,
            subissue=SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            findings=findings,
        )

    @staticmethod
    def _assigned(implementer: Mock) -> Assignment:
        assignment: Assignment = implementer.implement.call_args.args[0]
        return assignment

    def test_the_assignment_names_the_slice_and_the_issue_it_belongs_to(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        assigned = self._assigned(implementer)
        assert (assigned.issue, assigned.slice_id) == (SubIssueMother.pending().number, "slice-05")

    def test_what_the_slice_asks_for_travels_from_the_body_of_its_own_subissue(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        subissue = SubIssueMother.pending()
        assigned = self._assigned(implementer)
        assert (assigned.intention, assigned.criteria, assigned.signal) == (
            subissue.intention,
            subissue.criteria,
            subissue.signal,
        )

    def test_the_yardstick_and_the_controls_come_from_the_parent_because_the_slice_declares_neither(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        parent = ParentIssueMother.with_sources_and_controls()
        assigned = self._assigned(implementer)
        assert (assigned.sources, assigned.controls) == (parent.sources, parent.controls)

    def test_the_repo_that_is_assigned_is_the_worktree_where_the_work_happens(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        assert self._assigned(implementer).repo == _WORKTREE

    def test_a_first_round_assigns_no_findings_at_all(self, action: ImplementSlice, implementer: Mock) -> None:
        action.execute(self._params())

        assert self._assigned(implementer).findings == ()

    def test_a_second_round_assigns_the_findings_the_verifier_raised_so_the_retry_knows_what_to_fix(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        raised = FindingMother.with_line()

        action.execute(self._params(raised))

        assert self._assigned(implementer).findings == (raised,)

    def test_the_implementation_comes_back_without_being_reinterpreted(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        assert action.execute(self._params()) == ImplementationMother.of_two_paths()

    def test_the_log_of_a_control_in_red_is_assigned_as_a_path_because_nobody_who_judges_reads_build_output(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(replace(self._params(), control_logs=(ControlOutcomeMother.LOG,)))

        assert self._assigned(implementer).control_logs == (ControlOutcomeMother.LOG,)
