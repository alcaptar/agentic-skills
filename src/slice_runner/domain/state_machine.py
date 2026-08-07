from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, NoReturn

from slice_runner.domain.exceptions import ImpossibleTransitionError
from slice_runner.domain.outcome import Outcome
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step
from slice_runner.domain.transition import Transition

if TYPE_CHECKING:
    from slice_runner.domain.budgets import Budgets
    from slice_runner.domain.run import Run


@dataclass(frozen=True, kw_only=True, slots=True)
class StateMachine:
    budgets: Budgets

    def after(self, run: Run, outcome: Outcome) -> Transition:
        if run.step is Step.UNDERSTAND:
            self._impossible(run, outcome)
        if outcome is Outcome.OVER_BUDGET:
            return self._closed(run, RunState.ABORTED_BUDGET)

        return self._after_the_step_of(run, outcome)

    def _after_the_step_of(self, run: Run, outcome: Outcome) -> Transition:
        match run.step:
            case Step.UNDERSTAND:
                self._impossible(run, outcome)
            case Step.IMPLEMENT:
                return self._after_implementing(run, outcome)
            case Step.RUN_CONTROLS:
                return self._after_the_controls(run, outcome)
            case Step.VERIFY:
                return self._after_the_judge(run, outcome)
            case Step.OPEN_PULL_REQUEST:
                return self._after_the_pull_request(run, outcome)
            case Step.AWAIT_CI:
                return self._after_asking_the_ci(run, outcome)
            case Step.AWAIT_MERGE:
                return self._after_asking_for_the_merge(run, outcome)

    def _after_implementing(self, run: Run, outcome: Outcome) -> Transition:
        if outcome is Outcome.DONE:
            return self._moving_to(run, Step.RUN_CONTROLS)

        self._impossible(run, outcome)

    def _after_the_controls(self, run: Run, outcome: Outcome) -> Transition:
        match outcome:
            case Outcome.DONE:
                return self._moving_to(run, Step.VERIFY)
            case Outcome.FAILED:
                return self._retrying_a_mechanical_failure(run)
            case Outcome.HYGIENE_REJECTED:
                return self._retrying_a_hygiene_rejection(run)
            case Outcome.INDETERMINATE:
                return self._ticking(run)
            case _:
                self._impossible(run, outcome)

    def _retrying_a_mechanical_failure(self, run: Run) -> Transition:
        if run.control_retries < self.budgets.control_retries:
            return self._moving_to(replace(run, control_retries=run.control_retries + 1), Step.IMPLEMENT)

        return self._closed(run, RunState.BLOCKED_CONTROLS)

    def _retrying_a_hygiene_rejection(self, run: Run) -> Transition:
        if run.hygiene_retries < self.budgets.hygiene_retries:
            return self._moving_to(replace(run, hygiene_retries=run.hygiene_retries + 1), Step.IMPLEMENT)

        return self._closed(run, RunState.BLOCKED_HYGIENE)

    def _after_the_judge(self, run: Run, outcome: Outcome) -> Transition:
        match outcome:
            case Outcome.DONE:
                return self._moving_to(run, Step.OPEN_PULL_REQUEST)
            case Outcome.DISCARDED:
                return self._moving_to(replace(run, verify_discards=run.verify_discards + 1), Step.VERIFY)
            case Outcome.CORRECTIONS_ORDERED:
                return self._correcting_what_does_not_block(run)
            case Outcome.FAILED:
                return self._retrying_a_veto(run)
            case _:
                self._impossible(run, outcome)

    def _correcting_what_does_not_block(self, run: Run) -> Transition:
        if self._the_judge_still_has_budget(run):
            return self._back_to_implementing(run)

        return self._moving_to(run, Step.OPEN_PULL_REQUEST)

    def _retrying_a_veto(self, run: Run) -> Transition:
        if self._the_judge_still_has_budget(run):
            return self._back_to_implementing(run)

        return self._closed(run, RunState.BLOCKED_VERIFY)

    def _the_judge_still_has_budget(self, run: Run) -> bool:
        return run.verify_retries < self.budgets.verify_retries

    def _back_to_implementing(self, run: Run) -> Transition:
        return self._moving_to(replace(run, verify_retries=run.verify_retries + 1), Step.IMPLEMENT)

    def _after_the_pull_request(self, run: Run, outcome: Outcome) -> Transition:
        if outcome is Outcome.DONE:
            return self._moving_to(run, Step.AWAIT_CI)

        self._impossible(run, outcome)

    def _after_asking_the_ci(self, run: Run, outcome: Outcome) -> Transition:
        match outcome:
            case Outcome.DONE:
                return self._moving_to(self._answered(run), Step.AWAIT_MERGE)
            case Outcome.PENDING:
                return self._ticking(self._answered(run))
            case Outcome.INDETERMINATE:
                return self._counting_a_tick_with_no_answer(run)
            case Outcome.FAILED:
                return self._retrying_a_red_ci(self._answered(run))
            case _:
                self._impossible(run, outcome)

    def _counting_a_tick_with_no_answer(self, run: Run) -> Transition:
        counted = replace(run, indeterminate_ticks=run.indeterminate_ticks + 1)
        if counted.indeterminate_ticks < self.budgets.indeterminate_ticks:
            return self._ticking(counted)

        return self._closed(counted, RunState.BLOCKED_CI_INDETERMINATE)

    def _retrying_a_red_ci(self, run: Run) -> Transition:
        if run.ci_retries < self.budgets.ci_retries:
            return self._moving_to(replace(run, ci_retries=run.ci_retries + 1), Step.IMPLEMENT)

        return self._closed(run, RunState.BLOCKED_CI_RED)

    def _after_asking_for_the_merge(self, run: Run, outcome: Outcome) -> Transition:
        match outcome:
            case Outcome.DONE:
                return self._closed(run, RunState.MERGED)
            case Outcome.PENDING:
                return self._ticking(run)
            case _:
                self._impossible(run, outcome)

    @staticmethod
    def _answered(run: Run) -> Run:
        return replace(run, indeterminate_ticks=0)

    @staticmethod
    def _moving_to(run: Run, step: Step) -> Transition:
        return Transition(run=replace(run, step=step))

    def _ticking(self, run: Run) -> Transition:
        return Transition(run=run, wait_seconds=self.budgets.seconds_between_ticks)

    @staticmethod
    def _closed(run: Run, state: RunState) -> Transition:
        return Transition(run=run, state=state)

    @staticmethod
    def _impossible(run: Run, outcome: Outcome) -> NoReturn:
        raise ImpossibleTransitionError(f"the step `{run.step}` cannot come back with the outcome `{outcome}`")
