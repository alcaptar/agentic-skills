from __future__ import annotations

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
    def run(self, argv: list[str], *, stdin: str, cwd: str | None = None) -> ProcessOutput: ...
