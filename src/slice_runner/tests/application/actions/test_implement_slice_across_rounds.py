from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.implement_slice import ImplementSlice, ImplementSliceParams
from slice_runner.domain.debt_ledger import DebtLedger
from slice_runner.domain.design_captures_directory import DesignCapturesDirectory
from slice_runner.domain.diff_reader import DiffReader
from slice_runner.domain.implementer import Implementer
from slice_runner.infrastructure.process_design_capture_store import ProcessDesignCaptureStore
from slice_runner.tests.mothers.implementation_mother import ImplementationMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.assignment import Assignment
    from slice_runner.domain.implementation import Implementation


class _Rounds:
    LEFTOVER = "leftover.png"

    def __init__(self, worktree: Path, *, cites_a_design: bool) -> None:
        self._worktree = worktree
        self._directory = worktree / DesignCapturesDirectory.NAME
        self._cites_a_design = cites_a_design
        self.found_when_each_round_started: list[bool] = []
        implementer: Mock = create_autospec(Implementer, spec_set=True, instance=True)
        implementer.implement.side_effect = self._implementing
        self._action = ImplementSlice(
            implementer=implementer,
            reader=create_autospec(DiffReader, spec_set=True, instance=True),
            debt_ledger=create_autospec(DebtLedger, spec_set=True, instance=True),
            captures=ProcessDesignCaptureStore(process=Real.process()),
        )

    def _implementing(self, assignment: Assignment) -> Implementation:
        self.found_when_each_round_started.append((self._directory / self.LEFTOVER).exists())
        self._directory.mkdir(exist_ok=True)
        (self._directory / self.LEFTOVER).write_text("captured", encoding="utf-8")

        return ImplementationMother.of_two_paths()

    def run_two(self) -> None:
        params = ImplementSliceParams(
            repo="alcaptar/agentic-skills",
            worktree=str(self._worktree),
            subissue=SubIssueMother.naming_designs("detalle") if self._cites_a_design else SubIssueMother.pending(),
            parent=ParentIssueMother.declaring_two_designs(),
        )
        self._action.execute(params)
        self._action.execute(params)


@pytest.mark.integration
class TestWhatTheFirstRoundLeavesInTheCapturesDirectory:
    def test_a_file_left_at_the_end_of_round_one_does_not_exist_when_round_two_starts(self, tmp_path: Path) -> None:
        rounds = _Rounds(tmp_path, cites_a_design=True)

        rounds.run_two()

        assert rounds.found_when_each_round_started == [False, False]

    def test_a_slice_that_cites_no_design_keeps_what_is_in_the_directory(self, tmp_path: Path) -> None:
        rounds = _Rounds(tmp_path, cites_a_design=False)

        rounds.run_two()

        assert rounds.found_when_each_round_started == [False, True]
