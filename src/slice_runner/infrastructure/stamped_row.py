from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.infrastructure.durable_ledger import LedgerRow

if TYPE_CHECKING:
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class StampedRow(LedgerRow):
    ts: str
    repo: str
    issue: int
    slice_id: str

    @classmethod
    def _stamped(cls, coordinates: SliceCoordinates, *, ts: str, **fields: object) -> Self:
        return cls.model_validate(
            {
                "ts": ts,
                "repo": coordinates.repo,
                "issue": coordinates.issue,
                "slice_id": coordinates.slice_id.text,
                **fields,
            }
        )
