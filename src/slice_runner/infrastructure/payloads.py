from __future__ import annotations

import json
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from controles import valida_veredicto
from slice_runner.domain.verdict import Finding, InvalidVerdictError, Ruling, Severity, Verdict

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails

    from slice_runner.infrastructure.process import ProcessOutput


class JsonSchema:
    _DEFINITIONS = "$defs"
    _REFERENCE = "$ref"
    _NOISE = frozenset({"title"})

    @classmethod
    def flat(cls, model: type[BaseModel]) -> dict[str, object]:
        schema = model.model_json_schema(by_alias=True)
        definitions: dict[str, dict[str, object]] = schema.pop(cls._DEFINITIONS, {})

        return cls._resolved_object(schema, definitions)

    @classmethod
    def _resolved_object(cls, node: dict[str, object], definitions: dict[str, dict[str, object]]) -> dict[str, object]:
        reference = node.get(cls._REFERENCE)
        if isinstance(reference, str):
            return cls._resolved_object(definitions[reference.rsplit("/", 1)[-1]], definitions)

        return {key: cls._resolved(value, definitions) for key, value in node.items() if key not in cls._NOISE}

    @classmethod
    def _resolved(cls, node: object, definitions: dict[str, dict[str, object]]) -> object:
        if isinstance(node, dict):
            return cls._resolved_object(node, definitions)
        if isinstance(node, list):
            return [cls._resolved(item, definitions) for item in node]

        return node


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    @classmethod
    def _validated(cls, data: dict[str, object], where: str) -> Self:
        try:
            return cls.model_validate(data)
        except ValidationError as error:
            raise InvalidVerdictError(f"{where}: {cls._readable(error)}") from error

    @classmethod
    def _readable(cls, error: ValidationError) -> str:
        return "; ".join(cls._detail(reported) for reported in error.errors())

    @staticmethod
    def _detail(reported: ErrorDetails) -> str:
        where = ".".join(str(step) for step in reported["loc"])
        complaint = f"`{where}` {reported['msg'].lower()}"
        given = reported["input"]
        if isinstance(given, str | int | float | type(None)):
            return f"{complaint} (got {given!r})"

        return complaint

    def to_contract(self) -> dict[str, object]:
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")


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
    def from_dict(cls, data: dict[str, object]) -> VerdictPayload:
        payload = cls._validated(data, "the judge did not emit the verdict of the rubric")
        payload._reject_if_incoherent()

        return payload

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

    def _reject_if_incoherent(self) -> None:
        review = valida_veredicto(json.dumps(self.to_contract(), ensure_ascii=False))
        if not review.passed:
            raise InvalidVerdictError("; ".join(review.hallazgos))


class HarnessOutput(ContractModel):
    is_error: bool = Field(strict=True)
    structured_output: dict[str, object]

    api_error_status: object = None
    duration_api_ms: object = None
    duration_ms: object = None
    fast_mode_disabled_reason: object = None
    fast_mode_state: object = None
    model_usage: object = Field(alias="modelUsage", default=None)
    num_turns: object = None
    permission_denials: object = None
    result: object = None
    session_id: object = None
    stop_reason: object = None
    subtype: object = None
    terminal_reason: object = None
    time_to_request_ms: object = None
    total_cost_usd: object = None
    ttft_ms: object = None
    ttft_stream_ms: object = None
    type: object = None
    usage: object = None
    uuid: object = None

    @classmethod
    def from_process(cls, output: ProcessOutput) -> HarnessOutput:
        envelope = cls.from_dict(cls._decoded(output))
        if envelope.is_error:
            raise InvalidVerdictError("the harness marked the call as failed (`is_error`)")

        return envelope

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> HarnessOutput:
        return cls._validated(data, "the harness envelope is not the one we know")

    @classmethod
    def _decoded(cls, output: ProcessOutput) -> dict[str, object]:
        try:
            data = json.loads(output.stdout)
        except json.JSONDecodeError as error:
            raise InvalidVerdictError(
                f"the harness returned no JSON (code {output.code}): {cls._excerpt(output)}"
            ) from error
        if not isinstance(data, dict):
            raise InvalidVerdictError(f"the harness envelope has to be an object, not {type(data).__name__}")

        return data

    @staticmethod
    def _excerpt(output: ProcessOutput) -> str:
        return " ".join((output.stderr or output.stdout).split())[:200] or "(no output)"
