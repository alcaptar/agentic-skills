from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from slice_panel.infrastructure.herdr_json import HerdrJson
from slice_panel.infrastructure.herdr_payload_rejected import HerdrPayloadRejectedError

if TYPE_CHECKING:
    from slice_panel.domain.process_outcome import ProcessOutcome


class HerdrErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    code: str

    @model_validator(mode="before")
    @classmethod
    def projected(cls, data: object) -> object:
        return {"code": HerdrJson.at(data, "error", "code")}

    @classmethod
    def parsed(cls, text: str) -> Self:
        try:
            return cls.model_validate(HerdrJson.loaded(text, expected="an error"))
        except ValidationError as error:
            raise HerdrPayloadRejectedError("herdr answered an error without `error.code`") from error

    @classmethod
    def code_of(cls, outcome: ProcessOutcome) -> str:
        for text in (outcome.stdout, outcome.stderr):
            try:
                return cls.parsed(text).code
            except HerdrPayloadRejectedError:
                continue

        return ""
