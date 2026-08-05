from __future__ import annotations

import json
from dataclasses import dataclass, field

from slice_runner.infrastructure.judge_invocation import JudgeInvocation
from slice_runner.infrastructure.local_process import LocalProcess
from slice_runner.infrastructure.process import Process, ProcessNotRunnableError, ProcessOutput


class RecordedProcess(Process):
    def __init__(self, output: dict[str, object], *, code: int = 0) -> None:
        self._output = output
        self._code = code
        self.argv: list[str] = []
        self.stdin = ""
        self.cwd: str | None = None
        self.calls = 0

    def run(self, argv: list[str], *, stdin: str, cwd: str | None = None) -> ProcessOutput:
        self.argv = argv
        self.stdin = stdin
        self.cwd = cwd
        self.calls += 1

        return ProcessOutput(code=self._code, stdout=json.dumps(self._output), stderr="")


class UnrunnableJudge(Process):
    def __init__(self) -> None:
        self._real = LocalProcess()

    def run(self, argv: list[str], *, stdin: str, cwd: str | None = None) -> ProcessOutput:
        if argv[0] != JudgeInvocation.EXECUTABLE:
            return self._real.run(argv, stdin=stdin, cwd=cwd)

        raise ProcessNotRunnableError(f"{argv[0]}: no such executable")


@dataclass(frozen=True, kw_only=True, slots=True)
class RecordedCall:
    argv: list[str] = field(default_factory=list)
    stdin: str = ""


class ScriptedProcess(Process):
    def __init__(self, *outputs: ProcessOutput) -> None:
        self._outputs = list(outputs)
        self.calls: list[RecordedCall] = []

    def run(self, argv: list[str], *, stdin: str = "", cwd: str | None = None) -> ProcessOutput:
        self.calls.append(RecordedCall(argv=list(argv), stdin=stdin))

        return self._outputs.pop(0)


class RealExceptTheJudge(Process):
    def __init__(self, judge_output: dict[str, object]) -> None:
        self._judge_output = judge_output
        self._real = LocalProcess()
        self.argv: list[str] = []
        self.stdin = ""
        self.calls = 0

    def run(self, argv: list[str], *, stdin: str, cwd: str | None = None) -> ProcessOutput:
        if argv[0] != JudgeInvocation.EXECUTABLE:
            return self._real.run(argv, stdin=stdin, cwd=cwd)

        self.argv = argv
        self.stdin = stdin
        self.calls += 1

        return ProcessOutput(code=0, stdout=json.dumps(self._judge_output), stderr="")
