from __future__ import annotations

import json
from dataclasses import fields

import pytest

from slice_runner.domain.exceptions import InvalidVerdictError
from slice_runner.domain.finding import Finding
from slice_runner.domain.ruling import Ruling
from slice_runner.domain.severity import Severity
from slice_runner.infrastructure.verdict_payload import FindingPayload, VerdictPayload
from slice_runner.tests.mothers.judge_output_mother import JudgeVerdictMother
from slice_runner.tests.mothers.verdict_mother import FindingMother, VerdictMother


class TestTheContractVocabulary:
    def test_every_field_of_a_finding_has_a_payload_field_so_that_none_is_dropped_on_the_way_out(self) -> None:
        assert {declared.name for declared in fields(Finding)} == set(FindingPayload.model_fields)


class TestWhatTheProgramEmits:
    def test_a_finding_without_a_line_leaves_the_key_out_instead_of_emitting_null(self) -> None:
        emitted = FindingPayload.from_domain(FindingMother.without_line()).to_contract()

        assert "linea" not in emitted

    def test_a_finding_with_a_line_emits_it_as_an_integer_not_as_text(self) -> None:
        emitted = FindingPayload.from_domain(FindingMother.with_line(42)).to_contract()

        assert emitted["linea"] == 42

    def test_the_verdict_serialises_with_the_contract_vocabulary_not_with_the_domain_names(self) -> None:
        verdict = VerdictMother.failing(FindingMother.without_line())

        assert VerdictPayload.from_domain(verdict).to_contract() == {
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

    def test_a_verdict_survives_the_round_trip_through_the_contract_without_losing_a_field(self) -> None:
        verdict = VerdictMother.failing(FindingMother.with_line(11), FindingMother.without_line())

        assert VerdictPayload.from_domain(verdict).to_domain() == verdict


class TestTheSchemaTheJudgeReceives:
    def test_it_declares_every_finding_field_of_the_domain_under_its_contract_key(self) -> None:
        assert set(self._at("properties", "hallazgos", "items", "properties")) == FindingPayload.contract_keys()

    def test_it_requires_every_finding_field_but_the_line(self) -> None:
        required = self._at("properties", "hallazgos", "items")["required"]

        assert isinstance(required, list)
        assert set(required) == FindingPayload.contract_keys() - {"linea"}

    def test_it_closes_both_objects_so_the_judge_is_told_not_to_invent_keys(self) -> None:
        assert VerdictPayload.json_schema()["additionalProperties"] is False
        assert self._at("properties", "hallazgos", "items")["additionalProperties"] is False

    def test_it_spells_the_verdicts_out_as_an_enum(self) -> None:
        assert self._at("properties", "veredicto")["enum"] == [str(ruling) for ruling in Ruling]

    def test_it_spells_the_severities_out_as_an_enum(self) -> None:
        severidad = self._at("properties", "hallazgos", "items", "properties", "severidad")

        assert severidad["enum"] == [str(severity) for severity in Severity]

    def test_it_travels_with_no_reference_left_because_only_the_flat_form_has_been_measured(self) -> None:
        emitted = json.dumps(VerdictPayload.json_schema())

        assert "$ref" not in emitted
        assert "$defs" not in emitted

    @staticmethod
    def _at(*path: str) -> dict[str, object]:
        node: object = VerdictPayload.json_schema()
        for key in path:
            assert isinstance(node, dict)
            node = node[key]
        assert isinstance(node, dict)

        return node


class TestWhatTheJudgeIsAllowedToReturn:
    def test_a_verdict_with_no_findings_passes(self) -> None:
        payload = VerdictPayload.from_dict(JudgeVerdictMother.passing())

        assert payload.to_domain() == VerdictMother.passing()

    def test_the_finding_arrives_typed_down_to_its_severity(self) -> None:
        payload = VerdictPayload.from_dict(JudgeVerdictMother.failing())

        assert payload.findings[0].severity is Severity.HIGH

    def test_a_pass_that_comes_with_a_high_severity_finding_is_rejected(self) -> None:
        incoherent = JudgeVerdictMother.passing_with(JudgeVerdictMother.high_severity_finding())

        with pytest.raises(InvalidVerdictError, match="PASA with 1 finding"):
            VerdictPayload.from_dict(incoherent).to_domain()

    def test_a_key_we_do_not_know_in_a_finding_is_rejected_instead_of_ignored(self) -> None:
        invented = JudgeVerdictMother.high_severity_finding() | {"campo_nuevo_del_juez": "invented"}

        with pytest.raises(InvalidVerdictError, match="campo_nuevo_del_juez"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(invented))

    def test_a_finding_named_with_the_fields_of_the_domain_is_rejected_because_the_contract_is_the_rubric(self) -> None:
        in_english: dict[str, object] = {"rule": "boundaries", "path": "src/x.py", "severity": "alta"}

        with pytest.raises(InvalidVerdictError, match=r"`hallazgos\.0\.rule` extra inputs are not permitted"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(in_english))

    def test_a_severity_outside_the_rubric_is_rejected_saying_which_one_it_was(self) -> None:
        invented = JudgeVerdictMother.high_severity_finding() | {"severidad": "critica"}

        with pytest.raises(InvalidVerdictError, match="'critica'"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(invented))

    @pytest.mark.parametrize("line", [True, "11", 1.5])
    def test_a_line_that_is_not_an_integer_is_rejected_instead_of_coerced(self, line: object) -> None:
        with_a_bad_line = JudgeVerdictMother.high_severity_finding() | {"linea": line}

        with pytest.raises(InvalidVerdictError, match="linea"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(with_a_bad_line))

    def test_a_finding_missing_a_required_field_is_rejected_instead_of_defaulted(self) -> None:
        incomplete = {
            key: value for key, value in JudgeVerdictMother.high_severity_finding().items() if key != "detalle"
        }

        with pytest.raises(InvalidVerdictError, match="detalle"):
            VerdictPayload.from_dict(JudgeVerdictMother.failing(incomplete))
