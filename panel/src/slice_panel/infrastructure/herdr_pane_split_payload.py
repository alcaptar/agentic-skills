from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from slice_panel.infrastructure.herdr_json import HerdrJson
from slice_panel.infrastructure.herdr_payload_rejected import HerdrPayloadRejectedError


class HerdrPaneSplitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    pane_id: str

    @model_validator(mode="before")
    @classmethod
    def projected(cls, data: object) -> object:
        return {"pane_id": HerdrJson.at(data, "result", "pane", "pane_id")}

    @classmethod
    def parsed(cls, text: str) -> Self:
        try:
            return cls.model_validate(HerdrJson.loaded(text, expected="a pane split"))
        except ValidationError as error:
            raise HerdrPayloadRejectedError("herdr answered a pane split without `result.pane.pane_id`") from error
