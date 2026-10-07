from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from slice_panel.infrastructure.herdr_json import HerdrJson
from slice_panel.infrastructure.herdr_payload_rejected import HerdrPayloadRejectedError


class HerdrWorkspaceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    workspace_id: str
    label: str


class HerdrWorkspaceListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    workspaces: tuple[HerdrWorkspaceEntry, ...]

    @model_validator(mode="before")
    @classmethod
    def projected(cls, data: object) -> object:
        listed = HerdrJson.at(data, "result", "workspaces")
        if not isinstance(listed, list):
            return {"workspaces": None}

        return {
            "workspaces": [
                {"workspace_id": HerdrJson.at(entry, "workspace_id"), "label": HerdrJson.at(entry, "label")}
                for entry in listed
            ]
        }

    def labelled(self, label: str) -> tuple[str, ...]:
        return tuple(entry.workspace_id for entry in self.workspaces if entry.label == label)

    @classmethod
    def parsed(cls, text: str) -> Self:
        try:
            return cls.model_validate(HerdrJson.loaded(text, expected="a workspace list"))
        except ValidationError as error:
            raise HerdrPayloadRejectedError(
                "herdr answered a workspace list without `result.workspaces[].workspace_id` and `label`"
            ) from error
