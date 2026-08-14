from __future__ import annotations

from pathlib import Path
from typing import Self
from urllib.parse import urlparse

from pydantic import field_validator

from slice_runner.domain.exceptions import UnreadableProvenanceError
from slice_runner.infrastructure.contract_model import ContractModel


class DirectUrlPayload(ContractModel):
    url: str

    @field_validator("url")
    @classmethod
    def _is_a_local_checkout(cls, value: str) -> str:
        if urlparse(value).scheme != "file":
            raise ValueError(f"{value} is not a local file:// checkout")

        return value

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls._validated(
            cls._present(url=data.get("url")),
            "direct_url.json does not carry a readable url",
            UnreadableProvenanceError,
        )

    def to_domain(self) -> Path:
        return Path(urlparse(self.url).path)
