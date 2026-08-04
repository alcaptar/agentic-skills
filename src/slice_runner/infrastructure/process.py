from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class ProcessOutput:
    code: int
    stdout: str
    stderr: str


class ProcessNotRunnableError(OSError):
    pass


class Process(ABC):
    @abstractmethod
    def run(self, argv: list[str], *, stdin: str) -> ProcessOutput: ...


class LocalProcess(Process):
    def run(self, argv: list[str], *, stdin: str) -> ProcessOutput:
        try:
            finished = subprocess.run(argv, input=stdin, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise ProcessNotRunnableError(f"{argv[0]}: {exc.strerror or exc}") from exc

        return ProcessOutput(code=finished.returncode, stdout=finished.stdout, stderr=finished.stderr)
