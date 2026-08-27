from __future__ import annotations

from typing import TYPE_CHECKING, Self

from slice_runner.infrastructure.durable_ledger import LedgerRow

if TYPE_CHECKING:
    from slice_runner.domain.slice_coordinates import SliceCoordinates


class _CoordinatedRow(LedgerRow):
    ts: str | None = None
    repo: str | None = None
    issue: int | None = None
    slice_id: str | None = None

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


class StampedRow(_CoordinatedRow):
    ts: str
    repo: str
    issue: int
    slice_id: str


class LegacyTolerantStampedRow(_CoordinatedRow):
    pass


class SliceStampedRow(_CoordinatedRow):
    slice_id: str
