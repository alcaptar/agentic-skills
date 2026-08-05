from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class Budgets:
    control_retries: int = 2
    verify_retries: int = 2
    ci_retries: int = 1
    indeterminate_ticks: int = 3
    seconds_between_ticks: int = 30
