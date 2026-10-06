from __future__ import annotations

import json
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from slice_panel.infrastructure.validation_message import ValidationMessage


class UnderstandingRejectedError(ValueError):
    pass


class UnderstandingLinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=False)

    version: int = Field(strict=True)
    text: str

    @classmethod
    def parsed(cls, text: str) -> Self:
        try:
            return cls.model_validate(json.loads(text))
        except json.JSONDecodeError as error:
            raise UnderstandingRejectedError(f"the understanding output is not JSON: {error}") from error
        except ValidationError as error:
            raise UnderstandingRejectedError(
                f"the understanding output is not an understanding: {ValidationMessage.of(error)}"
            ) from error
