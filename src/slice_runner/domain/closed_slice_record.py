from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
    from slice_runner.domain.diff_stats import DiffStats
    from slice_runner.domain.discard_cause import DiscardCause
    from slice_runner.domain.recorded_spend import RecordedSpend
    from slice_runner.domain.run_state import RunState
    from slice_runner.domain.severity_count import SeverityCount


@dataclass(frozen=True, kw_only=True, slots=True)
class ClosedSliceRecord:
    ts: datetime
    repo: str
    issue: int
    slice_id: str
    name: str
    state: RunState
    findings: SeverityCount
    findings_of_the_last_round: SeverityCount
    implement_retries: int
    control_retries: int
    ci_retries: int
    verify_retries: int
    correction_retries: int
    verify_discards: int
    discard_cause: DiscardCause | None
    ci_indeterminate_cause: CiIndeterminateCause | None
    spend: RecordedSpend | None
    variant: str | None
    models: tuple[str, ...]
    debt: int
    diff: DiffStats | None
    budgets: dict[str, object]
    models_by_role: dict[str, object]
