from __future__ import annotations

from dataclasses import fields

from slice_runner.domain.verdict import FINDING_CONTRACT_KEYS, Finding, Ruling, Severity, Verdict

_WITHOUT_LINE = Finding(
    rule="cobertura-capa",
    path="src/x.py",
    severity=Severity.HIGH,
    evidence="the acceptance criterion has no test",
    detail="the test that accredits it is missing",
)


def test_a_finding_without_a_line_leaves_the_key_out_instead_of_emitting_null() -> None:
    assert "linea" not in _WITHOUT_LINE.to_dict()


def test_a_finding_with_a_line_emits_it_as_an_integer_not_as_text() -> None:
    with_line = Finding(
        rule="convenciones",
        path="src/x.py",
        severity=Severity.MEDIUM,
        evidence="prose in a `.py`",
        detail="the why lives in the pull request body",
        line=42,
    )

    assert with_line.to_dict()["linea"] == 42


def test_the_verdict_serialises_with_the_contract_vocabulary_not_with_the_domain_names() -> None:
    verdict = Verdict(ruling=Ruling.FAIL, findings=(_WITHOUT_LINE,))

    assert verdict.to_dict() == {
        "veredicto": "FALLA",
        "hallazgos": [
            {
                "regla": "cobertura-capa",
                "path": "src/x.py",
                "severidad": "alta",
                "evidencia": "the acceptance criterion has no test",
                "detalle": "the test that accredits it is missing",
            }
        ],
    }


def test_every_field_of_a_finding_has_a_contract_key_so_that_none_is_dropped_on_the_way_out() -> None:
    assert {f.name for f in fields(Finding)} == set(FINDING_CONTRACT_KEYS)
