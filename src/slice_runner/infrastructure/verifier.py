from __future__ import annotations

import json
from dataclasses import MISSING, dataclass, fields
from typing import TYPE_CHECKING

from controles import valida_veredicto
from slice_runner.domain.verdict import (
    FINDING_CONTRACT_KEYS,
    Finding,
    InvalidVerdictError,
    Ruling,
    Severity,
    Verdict,
)
from slice_runner.domain.verification import Verifier

if TYPE_CHECKING:
    from slice_runner.domain.verification import VerificationRequest
    from slice_runner.infrastructure.process import Process, ProcessOutput

_EXECUTABLE = "claude"

_JUDGE_TOOLS = ("Read", "Grep", "Glob", "Skill")

_FINDING_JSON_TYPES: dict[str, dict[str, object]] = {
    "rule": {"type": "string"},
    "path": {"type": "string"},
    "line": {"type": "integer"},
    "severity": {"type": "string", "enum": [str(s) for s in Severity]},
    "evidence": {"type": "string"},
    "detail": {"type": "string"},
}

_HARNESS_ENVELOPE_KEYS = frozenset(
    {
        "api_error_status",
        "duration_api_ms",
        "duration_ms",
        "fast_mode_disabled_reason",
        "fast_mode_state",
        "is_error",
        "modelUsage",
        "num_turns",
        "permission_denials",
        "result",
        "session_id",
        "stop_reason",
        "structured_output",
        "subtype",
        "terminal_reason",
        "time_to_request_ms",
        "total_cost_usd",
        "ttft_ms",
        "ttft_stream_ms",
        "type",
        "usage",
        "uuid",
    }
)

_FINDING_KEYS = frozenset(FINDING_CONTRACT_KEYS.values())


def verdict_schema() -> dict[str, object]:
    required = [FINDING_CONTRACT_KEYS[f.name] for f in fields(Finding) if f.default is MISSING]
    properties = {FINDING_CONTRACT_KEYS[name]: types for name, types in _FINDING_JSON_TYPES.items()}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["veredicto", "hallazgos"],
        "properties": {
            "veredicto": {"type": "string", "enum": [str(r) for r in Ruling]},
            "hallazgos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": required,
                    "properties": properties,
                },
            },
        },
    }


def _readable_dirs(request: VerificationRequest) -> list[str]:
    return [str(request.diff.slice_diff.parent), request.repo]


def verifier_argv(request: VerificationRequest) -> list[str]:
    granted = [arg for directory in _readable_dirs(request) for arg in ("--add-dir", directory)]
    return [
        _EXECUTABLE,
        "-p",
        "--output-format",
        "json",
        "--tools",
        ",".join(_JUDGE_TOOLS),
        *granted,
        "--strict-mcp-config",
        "--json-schema",
        json.dumps(verdict_schema(), ensure_ascii=False),
    ]


def _text(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise InvalidVerdictError(f"`{key}` has to be text, not {type(value).__name__}")
    return value


def _flag(data: dict[str, object], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise InvalidVerdictError(f"`{key}` has to be true or false, not {type(value).__name__}")
    return value


def _object(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise InvalidVerdictError(f"`{key}` has to be an object, not {type(value).__name__}")
    return value


def _array(data: dict[str, object], key: str) -> list[object]:
    value = data.get(key)
    if not isinstance(value, list):
        raise InvalidVerdictError(f"`{key}` has to be a list, not {type(value).__name__}")
    return value


def _line(data: dict[str, object]) -> int | None:
    key = FINDING_CONTRACT_KEYS["line"]
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidVerdictError(f"`{key}` has to be an integer, not {type(value).__name__}")
    return value


def _severity(data: dict[str, object]) -> Severity:
    value = _text(data, FINDING_CONTRACT_KEYS["severity"])
    if value not in tuple(Severity):
        raise InvalidVerdictError(f"invalid severity: {value!r}")
    return Severity(value)


def _reject_unknown_keys(data: dict[str, object], known: frozenset[str], where: str) -> None:
    unknown = sorted(set(data) - known)
    if unknown:
        raise InvalidVerdictError(f"unknown keys in {where}: {', '.join(unknown)}")


@dataclass(frozen=True, kw_only=True, slots=True)
class HarnessOutput:
    is_error: bool
    structured_output: dict[str, object]

    @staticmethod
    def from_dict(data: dict[str, object]) -> HarnessOutput:
        _reject_unknown_keys(data, _HARNESS_ENVELOPE_KEYS, "the harness envelope")
        return HarnessOutput(
            is_error=_flag(data, "is_error"),
            structured_output=_object(data, "structured_output"),
        )


def _finding_from(raw: object) -> Finding:
    if not isinstance(raw, dict):
        raise InvalidVerdictError(f"every finding has to be an object, not {type(raw).__name__}")
    _reject_unknown_keys(raw, _FINDING_KEYS, "a finding")
    return Finding(
        rule=_text(raw, FINDING_CONTRACT_KEYS["rule"]),
        path=_text(raw, FINDING_CONTRACT_KEYS["path"]),
        severity=_severity(raw),
        evidence=_text(raw, FINDING_CONTRACT_KEYS["evidence"]),
        detail=_text(raw, FINDING_CONTRACT_KEYS["detail"]),
        line=_line(raw),
    )


def _verdict_from(structure: dict[str, object]) -> Verdict:
    review = valida_veredicto(json.dumps(structure, ensure_ascii=False))
    if not review.passed:
        raise InvalidVerdictError("; ".join(review.hallazgos))
    return Verdict(
        ruling=Ruling(_text(structure, "veredicto")),
        findings=tuple(_finding_from(f) for f in _array(structure, "hallazgos")),
    )


def _prompt(request: VerificationRequest) -> str:
    return "\n".join(
        [
            request.instructions,
            "",
            "## Datos del run",
            "",
            f"- ruta del repo: {request.repo}",
            f"- `slice.diff`: {request.diff.slice_diff}",
            f"- `files.txt`: {request.diff.files} ({request.diff.n_files} ficheros)",
        ]
    )


def _envelope_from(output: ProcessOutput) -> HarnessOutput:
    try:
        data = json.loads(output.stdout)
    except json.JSONDecodeError as exc:
        reason = " ".join((output.stderr or output.stdout).split())[:200] or "(no output)"
        raise InvalidVerdictError(f"the harness returned no JSON (code {output.code}): {reason}") from exc
    if not isinstance(data, dict):
        raise InvalidVerdictError(f"the harness envelope has to be an object, not {type(data).__name__}")
    envelope = HarnessOutput.from_dict(data)
    if envelope.is_error:
        raise InvalidVerdictError("the harness marked the call as failed (`is_error`)")
    return envelope


class ClaudeVerifier(Verifier):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def verify(self, request: VerificationRequest) -> Verdict:
        output = self._process.run(verifier_argv(request), stdin=_prompt(request))
        return _verdict_from(_envelope_from(output).structured_output)
