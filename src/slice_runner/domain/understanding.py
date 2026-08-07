from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.harness_spend import HarnessSpend


@dataclass(frozen=True, kw_only=True, slots=True)
class Understanding:
    text: str
    spend: HarnessSpend
