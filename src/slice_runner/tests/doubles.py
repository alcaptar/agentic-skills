from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import Mock, create_autospec

from slice_runner.domain.call_trace import CallTrace
from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.process import (
    Process,
    ProcessNotRunnableError,
    ProcessOutput,
    ProcessTimedOutError,
)
from slice_runner.infrastructure.turn_log import TurnLog
from slice_runner.tests.real_process import Real

if TYPE_CHECKING:
    from collections.abc import Callable

    from slice_runner.domain.call_trace import HarnessCall
    from slice_runner.domain.step import Step
    from slice_runner.infrastructure.turn_log import HarnessTurn


class ProcessDoubles:
    @staticmethod
    def exiting(*, code: int = 0, stdout: str = "", stderr: str = "") -> Mock:
        process: Mock = create_autospec(Process, spec_set=True, instance=True)
        process.run.return_value = ProcessOutput(code=code, stdout=stdout, stderr=stderr)
        return process


class RecordedProcess(Process):
    def __init__(self, output: dict[str, object], *, code: int = 0) -> None:
        self._output = output
        self._code = code
        self.argv: list[str] = []
        self.stdin = ""
        self.cwd: str | None = None
        self.calls = 0

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.argv = argv
        self.stdin = stdin
        self.cwd = cwd
        self.calls += 1

        return ProcessOutput(code=self._code, stdout=json.dumps(self._output), stderr="")


class StreamingProcess(Process):
    def __init__(self, stdout: str, *, code: int = 0) -> None:
        self._stdout = stdout
        self._code = code
        self.argv: list[str] = []
        self.stdin = ""
        self.cwd: str | None = None

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.argv = argv
        self.stdin = stdin
        self.cwd = cwd
        if on_line is not None:
            for line in self._stdout.splitlines():
                if line.strip():
                    on_line(line)

        return ProcessOutput(code=self._code, stdout=self._stdout, stderr="")


class UnrunnableJudge(Process):
    def __init__(self) -> None:
        self._real = Real.process()

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        if argv[0] != JudgeInvocation.EXECUTABLE:
            return self._real.run(argv, stdin=stdin, cwd=cwd, on_line=on_line)

        raise ProcessNotRunnableError(f"{argv[0]}: no such executable")


class TimingOutProcess(Process):
    CAP_SECONDS: ClassVar[int] = 1

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        raise ProcessTimedOutError(f"{argv[0]}: killed after {self.CAP_SECONDS}s")


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordedCall:
    argv: list[str] = field(default_factory=list)
    stdin: str = ""


class ScriptedProcess(Process):
    def __init__(self, *outputs: ProcessOutput) -> None:
        self._outputs = list(outputs)
        self.calls: list[RecordedCall] = []

    def run(
        self,
        argv: list[str],
        *,
        stdin: str = "",
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.calls.append(RecordedCall(argv=list(argv), stdin=stdin))

        return self._outputs.pop(0)


@dataclass(frozen=True, kw_only=True, slots=True)
class Answer:
    to: tuple[str, ...]
    stdout: str = ""
    code: int = 0
    stderr: str = ""

    def answers(self, argv: list[str]) -> bool:
        return all(token in argv for token in self.to)

    @property
    def output(self) -> ProcessOutput:
        return ProcessOutput(code=self.code, stdout=self.stdout, stderr=self.stderr)


class AnsweringByArgv(Process):
    def __init__(self, *answers: Answer) -> None:
        self._answers = answers
        self.calls: list[RecordedCall] = []

    def run(
        self,
        argv: list[str],
        *,
        stdin: str = "",
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        self.calls.append(RecordedCall(argv=list(argv), stdin=stdin))
        for answer in self._answers:
            if answer.answers(argv):
                return answer.output

        raise AssertionError(f"no answer was scripted for `{' '.join(argv)}`")

    def invoked(self, *tokens: str) -> bool:
        return any(all(token in call.argv for token in tokens) for call in self.calls)

    def ran(self, *argv: str) -> bool:
        return list(argv) in [call.argv for call in self.calls]


class RealExceptTheJudge(Process):
    def __init__(self, judge_output: dict[str, object]) -> None:
        self._judge_output = judge_output
        self._real = Real.process()
        self.argv: list[str] = []
        self.stdin = ""
        self.calls = 0

    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput:
        if argv[0] != JudgeInvocation.EXECUTABLE:
            return self._real.run(argv, stdin=stdin, cwd=cwd, on_line=on_line)

        self.argv = argv
        self.stdin = stdin
        self.calls += 1

        return ProcessOutput(code=0, stdout=json.dumps(self._judge_output), stderr="")


class RecordedTrace(CallTrace):
    def __init__(self) -> None:
        self.calls: list[HarnessCall] = []

    def record(self, call: HarnessCall) -> None:
        self.calls.append(call)

    def sessions_of(self, *, slice_id: str, step: Step) -> tuple[str, ...]:
        return tuple(call.session for call in self.calls if call.slice_id == slice_id and call.step == step)


class RecordedTurnLog(TurnLog):
    def __init__(self) -> None:
        self.turns: list[HarnessTurn] = []

    def observe(self, turn: HarnessTurn) -> None:
        self.turns.append(turn)
