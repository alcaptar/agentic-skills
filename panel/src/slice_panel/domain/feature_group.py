from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_panel.domain.slice_view import SliceView


@dataclass(frozen=True, kw_only=True, slots=True)
class FeatureGroup:
    repo: str
    parent: int | None
    slices: tuple[SliceView, ...]
