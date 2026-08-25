from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.infrastructure.contract_model import ContractModel
from slice_runner.infrastructure.json_schema import JsonSchema

if TYPE_CHECKING:
    from slice_runner.domain.corpus_entry import CorpusEntry


class CorpusDiffPayload(ContractModel):
    slice_id: str
    verify_round: int
    session: str
    diff: str
    repo: str | None = None
    issue: int | None = None
    ts: str | None = None

    @classmethod
    def json_schema(cls) -> dict[str, object]:
        return JsonSchema.flat(cls)

    @classmethod
    def from_domain(cls, entry: CorpusEntry, *, ts: str) -> Self:
        return cls.model_validate(
            {
                "slice_id": entry.slice_id,
                "verify_round": entry.verify_round,
                "session": entry.session,
                "diff": entry.diff.text,
                "repo": entry.repo,
                "issue": entry.issue,
                "ts": ts,
            }
        )
