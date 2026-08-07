from __future__ import annotations

from enum import IntEnum

from slice_runner.domain.halt import Halt
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.run_state import RunState


class ExitCode(IntEnum):
    OK = 0
    VETOED = 1
    NO_USABLE_VERDICT = 2
    NO_DIFF = 3
    USAGE_ERROR = 4
    RUN_UNMERGED = 5
    WAIT_EXHAUSTED = 7
    PRECHECKS_BLOCKED = 8
    NO_SLICE_LEFT = 9
    RUN_INTERRUPTED = 10
    PULL_REQUEST_CLOSED = 11
    PROCESS_TIMED_OUT = 12

    @classmethod
    def of(cls, ruling: Ruling) -> ExitCode:
        match ruling:
            case Ruling.PASS:
                return cls.OK
            case Ruling.FAIL:
                return cls.VETOED

    @classmethod
    def of_the_halt(cls, *, halt: Halt, state: RunState) -> ExitCode:
        match halt:
            case Halt.RUN_CLOSED:
                return cls._of_the_closing(state)
            case Halt.PRECHECKS_BLOCKED:
                return cls.PRECHECKS_BLOCKED
            case Halt.WAIT_EXHAUSTED:
                return cls.WAIT_EXHAUSTED
            case Halt.PULL_REQUEST_CLOSED:
                return cls.PULL_REQUEST_CLOSED

    @classmethod
    def _of_the_closing(cls, state: RunState) -> ExitCode:
        match state:
            case RunState.MERGED:
                return cls.OK
            case (
                RunState.OPEN
                | RunState.BLOCKED_CONTROLS
                | RunState.BLOCKED_HYGIENE
                | RunState.BLOCKED_VERIFY
                | RunState.BLOCKED_CI_RED
                | RunState.BLOCKED_CI_INDETERMINATE
                | RunState.ABORTED_BUDGET
            ):
                return cls.RUN_UNMERGED
