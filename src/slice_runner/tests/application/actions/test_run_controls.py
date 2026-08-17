from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, create_autospec

import pytest

from slice_runner.application.actions.run_controls import RunControls, RunControlsParams
from slice_runner.domain.control_runner import ControlRunner
from slice_runner.domain.outcome import Outcome
from slice_runner.tests.mothers.control_command_mother import ControlCommandMother
from slice_runner.tests.mothers.control_outcome_mother import ControlOutcomeMother
from slice_runner.tests.mothers.parent_issue_mother import ParentIssueMother
from slice_runner.tests.mothers.sub_issue_mother import SubIssueMother

if TYPE_CHECKING:
    from slice_runner.domain.controls import Controls
    from slice_runner.domain.slice_identity import SliceIdentity

_WORKTREE = "/repos/agentic-skills"
_LOGS = Path("/tmp/slice-runner/logs")
_SLICE_ID: SliceIdentity = SubIssueMother.pending().slice_id


class TestRunControls:
    @pytest.fixture
    def controls_runner(self) -> Mock:
        runner: Mock = create_autospec(ControlRunner, spec_set=True, instance=True)
        runner.run.return_value = ControlOutcomeMother.green()
        return runner

    @pytest.fixture
    def action(self, controls_runner: Mock) -> RunControls:
        return RunControls(controls=controls_runner)

    @staticmethod
    def _params(*, controls: Controls, control_rounds_logged: int = 0) -> RunControlsParams:
        return RunControlsParams(
            worktree=_WORKTREE,
            controls=controls,
            logs=_LOGS,
            slice_id=_SLICE_ID,
            control_rounds_logged=control_rounds_logged,
        )

    def test_an_exempt_repo_runs_no_command(self, action: RunControls, controls_runner: Mock) -> None:
        result = action.execute(self._params(controls=ParentIssueMother.with_exempt_controls().controls))

        controls_runner.run.assert_not_called()
        assert result.outcome is Outcome.DONE

    def test_every_declared_command_runs_even_after_one_of_them_already_failed(
        self, action: RunControls, controls_runner: Mock
    ) -> None:
        controls_runner.run.side_effect = [ControlOutcomeMother.red(), ControlOutcomeMother.green()]

        action.execute(self._params(controls=ParentIssueMother.with_two_controls().controls))

        assert [call.args[0].name for call in controls_runner.run.call_args_list] == [
            ControlCommandMother.LINT_NAME,
            ControlCommandMother.TESTS_NAME,
        ]

    def test_the_round_directory_names_the_slice_and_the_next_round_after_what_was_already_logged(
        self, action: RunControls, controls_runner: Mock
    ) -> None:
        action.execute(
            self._params(controls=ParentIssueMother.with_sources_and_controls().controls, control_rounds_logged=1)
        )

        assert controls_runner.run.call_args.kwargs["out"] == _LOGS / _SLICE_ID.canonical / "round-2"
        assert controls_runner.run.call_args.kwargs["repo"] == _WORKTREE

    def test_a_red_controls_log_reaches_the_result_so_the_next_implementation_can_read_it(
        self, action: RunControls, controls_runner: Mock
    ) -> None:
        controls_runner.run.return_value = ControlOutcomeMother.red()

        result = action.execute(self._params(controls=ParentIssueMother.with_sources_and_controls().controls))

        assert result.red_logs == (ControlOutcomeMother.LOG,)
        assert result.outcome is Outcome.FAILED

    def test_a_control_that_could_not_be_measured_is_not_read_as_red(
        self, action: RunControls, controls_runner: Mock
    ) -> None:
        controls_runner.run.return_value = ControlOutcomeMother.unknown()

        result = action.execute(self._params(controls=ParentIssueMother.with_sources_and_controls().controls))

        assert result.red_logs == ()
        assert result.outcome is Outcome.INDETERMINATE
