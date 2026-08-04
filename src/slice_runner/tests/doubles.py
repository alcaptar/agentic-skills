from __future__ import annotations

import json

from slice_runner.infrastructure.process import Process, ProcessNotRunnableError, ProcessOutput


class RecordedProcess(Process):
    def __init__(self, output: dict[str, object], *, code: int = 0) -> None:
        self._output = output
        self._code = code
        self.argv: list[str] = []
        self.stdin = ""
        self.calls = 0

    def run(self, argv: list[str], *, stdin: str) -> ProcessOutput:
        self.argv = argv
        self.stdin = stdin
        self.calls += 1

        return ProcessOutput(code=self._code, stdout=json.dumps(self._output), stderr="")


class UnrunnableProcess(Process):
    def run(self, argv: list[str], *, stdin: str) -> ProcessOutput:
        raise ProcessNotRunnableError(f"{argv[0]}: no such executable")


class SpeechlessProcess(Process):
    def __init__(self, *, stderr: str, code: int = 1) -> None:
        self._stderr = stderr
        self._code = code

    def run(self, argv: list[str], *, stdin: str) -> ProcessOutput:
        return ProcessOutput(code=self._code, stdout="", stderr=self._stderr)
