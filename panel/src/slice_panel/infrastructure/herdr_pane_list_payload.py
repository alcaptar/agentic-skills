from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from slice_panel.infrastructure.herdr_json import HerdrJson
from slice_panel.infrastructure.herdr_payload_rejected import HerdrPayloadRejectedError


class HerdrPaneListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    cwds: tuple[Path, ...]

    @model_validator(mode="before")
    @classmethod
    def projected(cls, data: object) -> object:
        listed = HerdrJson.at(data, "result", "panes")
        if not isinstance(listed, list):
            return {"cwds": None}

        return {"cwds": [HerdrJson.at(pane, "cwd") for pane in listed]}

    @classmethod
    def parsed(cls, text: str) -> Self:
        try:
            return cls.model_validate(HerdrJson.loaded(text, expected="a pane list"))
        except ValidationError as error:
            raise HerdrPayloadRejectedError("herdr answered a pane list without `result.panes[].cwd`") from error
