from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.diff_on_disk import DiffOnDisk


@dataclass(frozen=True, kw_only=True, slots=True)
class VerificationRequest:
    repo: str
    instructions: str
    diff: DiffOnDisk
