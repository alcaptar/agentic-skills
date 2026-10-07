from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from collections.abc import Sequence


class UnboundedProcesses(ABC):
    @abstractmethod
    def spawned_detached(self, argv: Sequence[str]) -> None: ...

    @abstractmethod
    def replaced_by(self, argv: Sequence[str]) -> NoReturn: ...
