from __future__ import annotations

import json
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from slice_panel.domain.follow_line import FollowLine


class FollowLineRejectedError(ValueError):
    pass


class FollowLinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    ts: datetime
    repo: str
    issue: int = Field(strict=True)
    slice_id: str
    step: str
    status: str
    cost_usd: float
    parent: int | None = Field(default=None, strict=True)
    name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def projected(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        return {key: value for key, value in data.items() if key in cls.model_fields}

    @classmethod
    def parsed(cls, line: str) -> Self:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            raise FollowLineRejectedError(f"the line is not JSON: {line!r}") from error
        try:
            return cls.model_validate(data)
        except ValidationError as error:
            raise FollowLineRejectedError(f"the line is not a follow line: {cls._readable(error)}") from error

    @staticmethod
    def _readable(error: ValidationError) -> str:
        return "; ".join(
            f"`{'.'.join(str(step) for step in each['loc'])}` {each['msg'].lower()}" for each in error.errors()
        )

    def to_domain(self) -> FollowLine:
        return FollowLine(
            ts=self.ts,
            repo=self.repo,
            issue=self.issue,
            slice_id=self.slice_id,
            step=self.step,
            status=self.status,
            cost_usd=self.cost_usd,
            parent=self.parent,
            name=self.name,
        )
