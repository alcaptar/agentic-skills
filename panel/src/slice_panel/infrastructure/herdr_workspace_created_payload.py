from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from slice_panel.domain.created_workspace import CreatedWorkspace
from slice_panel.infrastructure.herdr_json import HerdrJson
from slice_panel.infrastructure.herdr_payload_rejected import HerdrPayloadRejectedError


class HerdrWorkspaceCreatedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    workspace_id: str
    pane_id: str

    @model_validator(mode="before")
    @classmethod
    def projected(cls, data: object) -> object:
        return {
            "workspace_id": HerdrJson.at(data, "result", "workspace", "workspace_id"),
            "pane_id": HerdrJson.at(data, "result", "root_pane", "pane_id"),
        }

    def to_domain(self) -> CreatedWorkspace:
        return CreatedWorkspace(workspace_id=self.workspace_id, root_pane=self.pane_id)

    @classmethod
    def parsed(cls, text: str) -> Self:
        try:
            return cls.model_validate(HerdrJson.loaded(text, expected="a workspace creation"))
        except ValidationError as error:
            raise HerdrPayloadRejectedError(
                "herdr answered a workspace creation without `result.workspace.workspace_id` "
                "and `result.root_pane.pane_id`"
            ) from error
