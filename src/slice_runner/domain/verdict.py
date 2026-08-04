from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.ruling import Ruling


@dataclass(frozen=True, kw_only=True, slots=True)
class Verdict:
    ruling: Ruling
    findings: tuple[Finding, ...] = field(default_factory=tuple)
