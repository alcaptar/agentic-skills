from __future__ import annotations

from slice_runner.domain.finding import Finding
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity
from slice_runner.domain.verdict import Verdict


class FindingMother:
    @staticmethod
    def without_line(
        *,
        rule: str = "cobertura-capa",
        path: str = "src/x.py",
        severity: Severity = Severity.HIGH,
    ) -> Finding:
        return Finding(
            rule=rule,
            path=path,
            severity=severity,
            evidence="the acceptance criterion has no test",
            detail="the test that accredits it is missing",
        )

    @staticmethod
    def with_line(line: int = 42) -> Finding:
        return Finding(
            rule="convenciones",
            path="src/x.py",
            severity=Severity.MEDIUM,
            evidence="prose in a `.py`",
            detail="the why lives in the pull request body",
            line=line,
        )

    @staticmethod
    def low_severity(*, path: str = "src/x.py") -> Finding:
        return Finding(
            rule="nombrado",
            path=path,
            severity=Severity.LOW,
            evidence="una constante sin nombre",
            detail="queda para otra vuelta, no bloquea la entrega",
        )


class VerdictMother:
    @staticmethod
    def passing() -> Verdict:
        return Verdict(ruling=Ruling.PASS)

    @staticmethod
    def failing(*findings: Finding) -> Verdict:
        return Verdict(ruling=Ruling.FAIL, findings=findings or (FindingMother.without_line(),))

    @staticmethod
    def passing_with(*findings: Finding) -> Verdict:
        return Verdict(ruling=Ruling.PASS, findings=findings or (FindingMother.with_line(),))
