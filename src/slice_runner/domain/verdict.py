from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Ruling(StrEnum):
    PASS = "PASA"
    FAIL = "FALLA"


class Severity(StrEnum):
    HIGH = "alta"
    MEDIUM = "media"
    LOW = "baja"


@dataclass(frozen=True, kw_only=True, slots=True)
class Finding:
    rule: str
    path: str
    severity: Severity
    evidence: str
    detail: str
    line: int | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class Verdict:
    ruling: Ruling
    findings: tuple[Finding, ...] = field(default_factory=tuple)


class InvalidVerdictError(ValueError):
    pass
