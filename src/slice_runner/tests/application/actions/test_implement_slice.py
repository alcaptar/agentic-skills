from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.implement_slice import ImplementSlice, ImplementSliceParams
from slice_runner.domain.diff_reader import DiffReader
from slice_runner.domain.implementer import Implementer
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.mothers.verdict_mother import FindingMother

if TYPE_CHECKING:
    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.sub_issue import SubIssue

_REPO = "alcaptar/agentic-skills"
_WORKTREE = "/repos/agentic-skills"


class TestImplementSlice:
    @pytest.fixture
    def implementer(self) -> Mock:
        implementer: Mock = create_autospec(Implementer, spec_set=True, instance=True)
        implementer.implement.return_value = ImplementationMother.of_two_paths()
        return implementer

    @pytest.fixture
    def reader(self) -> Mock:
        reader: Mock = create_autospec(DiffReader, spec_set=True, instance=True)
        reader.dirty.return_value = ()
        return reader

    @pytest.fixture
    def action(self, implementer: Mock, reader: Mock) -> ImplementSlice:
        return ImplementSlice(implementer=implementer, reader=reader)

    @staticmethod
    def _params(
        *findings: Finding, subissue: SubIssue | None = None, previous_call_died: bool = False
    ) -> ImplementSliceParams:
        return ImplementSliceParams(
            repo=_REPO,
            worktree=_WORKTREE,
            subissue=subissue or SubIssueMother.pending(),
            parent=ParentIssueMother.with_sources_and_controls(),
            findings=findings,
            previous_call_died=previous_call_died,
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

    def test_a_slice_carrying_a_user_story_is_assigned_by_its_canonical_identifier_not_the_bare_ordinal(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params(subissue=SubIssueMother.carrying_a_user_story()))

        assert self._assigned(implementer).slice_id == "PROJ-1234-05"

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

    def test_the_worktree_that_is_assigned_is_where_the_work_happens(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        assert self._assigned(implementer).worktree == _WORKTREE

    def test_the_repo_that_is_assigned_is_the_real_repo_of_the_issue_and_not_the_worktree(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        assert self._assigned(implementer).repo == _REPO

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

    def test_the_refusal_of_a_dirty_index_is_assigned_because_otherwise_the_round_repeats_it_blind(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(replace(self._params(), hygiene_refusal="src/leftover.py (not-declared)"))

        assert self._assigned(implementer).hygiene_refusal == "src/leftover.py (not-declared)"

    def test_what_the_person_agreed_to_in_the_alignment_is_assigned_so_the_round_is_ruled_by_it(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(replace(self._params(), understanding="el contador vive en Run, no en el conductor"))

        assert self._assigned(implementer).understanding == "el contador vive en Run, no en el conductor"

    def test_a_slice_conducted_without_an_alignment_assigns_no_understanding_at_all(
        self, action: ImplementSlice, implementer: Mock
    ) -> None:
        action.execute(self._params())

        assert self._assigned(implementer).understanding == ""

    def test_a_previous_call_that_died_asks_the_reader_and_assigns_the_files_it_found_dirty(
        self, action: ImplementSlice, implementer: Mock, reader: Mock
    ) -> None:
        reader.dirty.return_value = ("src/leftover.py",)

        action.execute(self._params(previous_call_died=True))

        reader.dirty.assert_called_once_with(worktree=_WORKTREE)
        assert self._assigned(implementer).dirty_worktree_files == ("src/leftover.py",)

    def test_a_round_that_did_not_follow_a_dead_call_never_asks_the_reader_and_assigns_no_file(
        self, action: ImplementSlice, implementer: Mock, reader: Mock
    ) -> None:
        action.execute(self._params(previous_call_died=False))

        reader.dirty.assert_not_called()
        assert self._assigned(implementer).dirty_worktree_files == ()
