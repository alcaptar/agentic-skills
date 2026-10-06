from __future__ import annotations

from typing import ClassVar, Self

from slice_runner.infrastructure.contract_model import ContractModel


class UnderstandingLinePayload(ContractModel):
    VERSION: ClassVar[int] = 1

    version: int
    text: str

    @classmethod
    def from_domain(cls, text: str) -> Self:
        return cls(version=cls.VERSION, text=text)
