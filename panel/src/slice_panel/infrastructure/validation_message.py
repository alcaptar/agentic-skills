from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import ValidationError


class ValidationMessage:
    @staticmethod
    def of(error: ValidationError) -> str:
        return "; ".join(
            f"`{'.'.join(str(step) for step in each['loc'])}` {each['msg'].lower()}" for each in error.errors()
        )
