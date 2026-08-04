from __future__ import annotations

from typing import Self

from pydantic import Field

from slice_runner.domain.finding import Finding
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity
from slice_runner.domain.verdict import Verdict
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema


class FindingPayload(ContractModel):
    rule: str = Field(alias="regla")
    path: str = Field(alias="path")
    severity: Severity = Field(alias="severidad")
    evidence: str = Field(alias="evidencia")
    detail: str = Field(alias="detalle")
    line: int | None = Field(alias="linea", default=None, strict=True)

    @classmethod
    def contract_keys(cls) -> set[str]:
        return {str(declared.alias) for declared in cls.model_fields.values()}

    @classmethod
    def from_domain(cls, finding: Finding) -> Self:
        return cls.model_validate(
            {
                "regla": finding.rule,
                "path": finding.path,
                "severidad": finding.severity,
                "evidencia": finding.evidence,
                "detalle": finding.detail,
                "linea": finding.line,
            }
        )

    def to_domain(self) -> Finding:
        return Finding(
            rule=self.rule,
            path=self.path,
            severity=self.severity,
            evidence=self.evidence,
            detail=self.detail,
            line=self.line,
        )


class VerdictPayload(ContractModel):
    ruling: Ruling = Field(alias="veredicto")
    findings: list[FindingPayload] = Field(alias="hallazgos")

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "the judge did not emit the verdict of the rubric")

    @classmethod
    def from_domain(cls, verdict: Verdict) -> Self:
        return cls.model_validate(
            {
                "veredicto": verdict.ruling,
                "hallazgos": [FindingPayload.from_domain(finding) for finding in verdict.findings],
            }
        )

    def to_domain(self) -> Verdict:
        return Verdict(ruling=self.ruling, findings=tuple(finding.to_domain() for finding in self.findings))
