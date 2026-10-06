from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class SliceListing:
    repo: str
    parent: int
    issue: int
    slice_id: str
    name: str
    label: str | None
    closed: bool
    cost_usd: float | None
    pull_request: int | None
