from __future__ import annotations

import json
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


class HerdrTabCreatedRejectedError(ValueError):
    pass


class HerdrTabCreatedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    tab_id: str
    pane_id: str

    @model_validator(mode="before")
    @classmethod
    def projected(cls, data: object) -> object:
        return {
            "tab_id": cls._at(data, "result", "tab", "tab_id"),
            "pane_id": cls._at(data, "result", "root_pane", "pane_id"),
        }

    @staticmethod
    def _at(data: object, *path: str) -> object:
        for key in path:
            if not isinstance(data, dict) or key not in data:
                return None
            data = data[key]

        return data

    @classmethod
    def parsed(cls, text: str) -> Self:
        try:
            return cls.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as error:
            raise HerdrTabCreatedRejectedError(
                "herdr answered a tab creation without `result.tab.tab_id` and `result.root_pane.pane_id`"
            ) from error
