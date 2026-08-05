from __future__ import annotations

import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, Self

from pydantic import Field

from slice_runner.domain.exceptions import InvalidHarnessOutputError, MeasuredCallError
from slice_runner.domain.harness_spend import HarnessSpend
from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.permission_denial import PermissionDenial

if TYPE_CHECKING:
    from collections.abc import Iterator

    from slice_runner.infrastructure.process import ProcessOutput


class HarnessOutput(ContractModel):
    is_error: bool = Field(strict=True)
    structured_output: dict[str, object]

    api_error_status: object = None
    duration_api_ms: object = None
    duration_ms: int
    fast_mode_disabled_reason: object = None
    fast_mode_state: object = None
    model_usage: object = Field(alias="modelUsage", default=None)
    num_turns: int
    permission_denials: tuple[PermissionDenial, ...] = ()
    result: object = None
    session_id: object = None
    stop_reason: object = None
    subtype: object = None
    terminal_reason: object = None
    time_to_request_ms: object = None
    total_cost_usd: float
    ttft_ms: object = None
    ttft_stream_ms: object = None
    type: object = None
    usage: object = None
    uuid: object = None

    def to_domain(self) -> HarnessSpend:
        return HarnessSpend.of_a_call(cost_usd=self.total_cost_usd, turns=self.num_turns, duration_ms=self.duration_ms)

    @contextmanager
    def measuring(self) -> Iterator[None]:
        try:
            yield
        except MeasuredCallError as error:
            error.spend = self.to_domain()
            raise

    @classmethod
    def from_process(cls, output: ProcessOutput) -> Self:
        envelope = cls.from_dict(cls._decoded(output))
        with envelope.measuring():
            if envelope.is_error:
                raise InvalidHarnessOutputError("the harness marked the call as failed (`is_error`)")

        return envelope

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(data, "the harness envelope is not the one we know", InvalidHarnessOutputError)

    @classmethod
    def _decoded(cls, output: ProcessOutput) -> dict[str, object]:
        try:
            data = json.loads(output.stdout)
        except json.JSONDecodeError as error:
            raise InvalidHarnessOutputError(
                f"the harness returned no JSON (code {output.code}): {cls._excerpt(output)}"
            ) from error
        if not isinstance(data, dict):
            raise InvalidHarnessOutputError(f"the harness envelope has to be an object, not {type(data).__name__}")

        return data

    @staticmethod
    def _excerpt(output: ProcessOutput) -> str:
        return " ".join((output.stderr or output.stdout).split())[:200] or "(no output)"
