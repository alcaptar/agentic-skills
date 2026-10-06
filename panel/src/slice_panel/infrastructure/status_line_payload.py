from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from slice_panel.domain.slice_listing import SliceListing
from slice_panel.infrastructure.validation_message import ValidationMessage


class StatusRejectedError(ValueError):
    pass


class StatusLinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    version: int = Field(strict=True)
    slice_id: str
    name: str
    issue: int = Field(strict=True)
    closed: bool = Field(strict=True)
    label: str | None = None
    cost_usd: float | None = None
    pull_request: int | None = Field(default=None, strict=True)

    @classmethod
    def listings_of(cls, text: str, *, repo: str, parent: int) -> tuple[SliceListing, ...]:
        try:
            payloads = [cls.model_validate(json.loads(line)) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError as error:
            raise StatusRejectedError(f"the status output is not JSON: {error}") from error
        except ValidationError as error:
            raise StatusRejectedError(f"the status output is not a slice: {ValidationMessage.of(error)}") from error

        return tuple(each.to_domain(repo=repo, parent=parent) for each in payloads)

    def to_domain(self, *, repo: str, parent: int) -> SliceListing:
        return SliceListing(
            repo=repo,
            parent=parent,
            issue=self.issue,
            slice_id=self.slice_id,
            name=self.name,
            label=self.label,
            closed=self.closed,
            cost_usd=self.cost_usd,
            pull_request=self.pull_request,
        )
