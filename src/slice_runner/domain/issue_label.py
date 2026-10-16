from __future__ import annotations

from enum import StrEnum

from slice_runner.domain.closing_reason import ClosingReason
from slice_runner.domain.closure import Closure
from slice_runner.domain.run_state import RunState
from slice_runner.domain.step import Step


class IssueLabel(StrEnum):
    PENDING = "estado:pendiente"
    IN_PROGRESS = "estado:en-curso"
    AWAITING_MERGE = "estado:esperando-merge"
    BLOCKED_CONTROLS = "bloqueada:controles"
    BLOCKED_HYGIENE = "bloqueada:higiene"
    BLOCKED_VERIFY = "bloqueada:verify"
    BLOCKED_UNCHANGED_DIFF = "bloqueada:sin-cambios"
    BLOCKED_CI_RED = "bloqueada:ci-roja"
    BLOCKED_CI_INDETERMINATE = "bloqueada:ci-indeterminada"
    BLOCKED_CI_CONFLICT = "bloqueada:conflicto"
    BLOCKED_WORKTREE = "bloqueada:worktree"
    BLOCKED_LEFTOVER_WORKTREE = "bloqueada:worktree-sin-retirar"
    ABORTED_BUDGET = "abortada:presupuesto"
    ABORTED_UNMEASURED_CALL = "abortada:llamada-no-medida"

    @property
    def closed_as(self) -> Closure | None:
        for reason in ClosingReason:
            closure = Closure.because_of(reason)
            if IssueLabel.of(closure=closure, step=Step.MOUNT_WORKTREE) is self:
                return closure

        return None

    @classmethod
    def of(cls, *, closure: Closure, step: Step) -> IssueLabel | None:
        match closure.state:
            case RunState.OPEN:
                return cls._of_the_open_step(step)
            case RunState.MERGED:
                return None
            case RunState.BLOCKED | RunState.ABORTED:
                return cls._of_the_closed(closure)

    @classmethod
    def _of_the_open_step(cls, step: Step) -> IssueLabel:
        match step:
            case Step.AWAIT_MERGE:
                return cls.AWAITING_MERGE
            case (
                Step.MOUNT_WORKTREE
                | Step.UNDERSTAND
                | Step.IMPLEMENT
                | Step.RUN_CONTROLS
                | Step.VERIFY
                | Step.OPEN_PULL_REQUEST
                | Step.AWAIT_CI
                | Step.CATCH_UP
            ):
                return cls.IN_PROGRESS

    @classmethod
    def _of_the_closed(cls, closure: Closure) -> IssueLabel:
        return {
            Closure.because_of(ClosingReason.CONTROLS): cls.BLOCKED_CONTROLS,
            Closure.because_of(ClosingReason.HYGIENE): cls.BLOCKED_HYGIENE,
            Closure.because_of(ClosingReason.VERIFY): cls.BLOCKED_VERIFY,
            Closure.because_of(ClosingReason.UNCHANGED_DIFF): cls.BLOCKED_UNCHANGED_DIFF,
            Closure.because_of(ClosingReason.CI_RED): cls.BLOCKED_CI_RED,
            Closure.because_of(ClosingReason.CI_INDETERMINATE): cls.BLOCKED_CI_INDETERMINATE,
            Closure.because_of(ClosingReason.CI_CONFLICT): cls.BLOCKED_CI_CONFLICT,
            Closure.because_of(ClosingReason.WORKTREE): cls.BLOCKED_WORKTREE,
            Closure.because_of(ClosingReason.LEFTOVER_WORKTREE): cls.BLOCKED_LEFTOVER_WORKTREE,
            Closure.because_of(ClosingReason.BUDGET): cls.ABORTED_BUDGET,
            Closure.because_of(ClosingReason.UNMEASURED_CALL): cls.ABORTED_UNMEASURED_CALL,
        }[closure]
