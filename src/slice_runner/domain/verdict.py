from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class Ruling(StrEnum):
    PASS = "PASA"
    FAIL = "FALLA"


class Severity(StrEnum):
    HIGH = "alta"
    MEDIUM = "media"
    LOW = "baja"


FINDING_CONTRACT_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "rule": "regla",
        "path": "path",
        "severity": "severidad",
        "evidence": "evidencia",
        "detail": "detalle",
        "line": "linea",
    }
)


@dataclass(frozen=True, kw_only=True, slots=True)
class Finding:
    rule: str
    path: str
    severity: Severity
    evidence: str
    detail: str
    line: int | None = None

    def to_dict(self) -> dict[str, object]:
        emitted: dict[str, object] = {
            FINDING_CONTRACT_KEYS["rule"]: self.rule,
            FINDING_CONTRACT_KEYS["path"]: self.path,
            FINDING_CONTRACT_KEYS["severity"]: str(self.severity),
            FINDING_CONTRACT_KEYS["evidence"]: self.evidence,
            FINDING_CONTRACT_KEYS["detail"]: self.detail,
        }
        if self.line is not None:
            emitted[FINDING_CONTRACT_KEYS["line"]] = self.line
        return emitted


@dataclass(frozen=True, kw_only=True, slots=True)
class Verdict:
    ruling: Ruling
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {"veredicto": str(self.ruling), "hallazgos": [f.to_dict() for f in self.findings]}


class InvalidVerdictError(ValueError):
    pass
