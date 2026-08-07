from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, kw_only=True, slots=True)
class ProcessOutput:
    code: int
    stdout: str
    stderr: str


class ProcessNotRunnableError(OSError):
    pass


class ProcessTimedOutError(OSError):
    pass


class Process(ABC):
    @abstractmethod
    def run(
        self,
        argv: list[str],
        *,
        stdin: str,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> ProcessOutput: ...
