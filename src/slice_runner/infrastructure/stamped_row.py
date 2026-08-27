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
    def may_belong_to(cls, data: dict[str, object], coordinates: SliceCoordinates) -> bool:
        wanted: dict[str, object] = {
            "repo": coordinates.repo,
            "issue": coordinates.issue,
            "slice_id": coordinates.slice_id.text,
        }

        return all(data.get(key) == value for key, value in wanted.items() if key in data)

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
