from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step


class IssueLabel(StrEnum):
    PENDING = "estado:pendiente"
    AWAITING_ALIGNMENT = "estado:esperando-alineacion"
    IN_PROGRESS = "estado:en-curso"
    AWAITING_MERGE = "estado:esperando-merge"
    BLOCKED_CONTROLS = "bloqueada:controles"
    BLOCKED_HYGIENE = "bloqueada:higiene"
    BLOCKED_VERIFY = "bloqueada:verify"
    BLOCKED_CI_RED = "bloqueada:ci-roja"
    BLOCKED_CI_INDETERMINATE = "bloqueada:ci-indeterminada"
    BLOCKED_CI_CONFLICT = "bloqueada:conflicto"
    ABORTED_BUDGET = "abortada:presupuesto"

    @classmethod
    def of(cls, *, state: RunState, step: Step) -> IssueLabel | None:
        match state:
            case RunState.OPEN:
                return cls._of_the_open_step(step)
            case RunState.MERGED:
                return None
            case (
                RunState.BLOCKED_CONTROLS
                | RunState.BLOCKED_HYGIENE
                | RunState.BLOCKED_VERIFY
                | RunState.BLOCKED_CI_RED
                | RunState.BLOCKED_CI_INDETERMINATE
                | RunState.BLOCKED_CI_CONFLICT
            ):
                return cls._of_the_blocked_reason(state)
            case RunState.ABORTED_BUDGET:
                return cls.ABORTED_BUDGET

    @classmethod
    def _of_the_open_step(cls, step: Step) -> IssueLabel:
        match step:
            case Step.UNDERSTAND:
                return cls.AWAITING_ALIGNMENT
            case Step.AWAIT_MERGE:
                return cls.AWAITING_MERGE
            case Step.IMPLEMENT | Step.RUN_CONTROLS | Step.VERIFY | Step.OPEN_PULL_REQUEST | Step.AWAIT_CI:
                return cls.IN_PROGRESS

    @classmethod
    def _of_the_blocked_reason(cls, state: RunState) -> IssueLabel:
        return {
            RunState.BLOCKED_CONTROLS: cls.BLOCKED_CONTROLS,
            RunState.BLOCKED_HYGIENE: cls.BLOCKED_HYGIENE,
            RunState.BLOCKED_VERIFY: cls.BLOCKED_VERIFY,
            RunState.BLOCKED_CI_RED: cls.BLOCKED_CI_RED,
            RunState.BLOCKED_CI_INDETERMINATE: cls.BLOCKED_CI_INDETERMINATE,
            RunState.BLOCKED_CI_CONFLICT: cls.BLOCKED_CI_CONFLICT,
        }[state]
