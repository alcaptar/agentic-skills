from __future__ import annotations

import json
from typing import TYPE_CHECKING, Self

from pydantic import Field

from slice_runner.domain.exceptions import InvalidVerdictError
from slice_runner.infrastructure.contract_model import ContractModel

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import ProcessOutput


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
    def from_process(cls, output: ProcessOutput) -> Self:
        envelope = cls.from_dict(cls._decoded(output))
        if envelope.is_error:
            raise InvalidVerdictError("the harness marked the call as failed (`is_error`)")

        return envelope

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
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
