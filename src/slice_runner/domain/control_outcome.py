from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.domain.ruling import Ruling


@dataclass(frozen=True, kw_only=True, slots=True)
class ControlOutcome:
    ruling: Ruling
    log: Path
