from __future__ import annotations

from dataclasses import dataclass, field
from functools import reduce
from typing import TYPE_CHECKING

from slice_runner.domain.harness_spend import HarnessSpend

if TYPE_CHECKING:
    from slice_runner.domain.discard_cause import DiscardCause
    from slice_runner.domain.finding import Finding
    from slice_runner.domain.run import Run
    from slice_runner.domain.run_state import RunState
    from slice_runner.domain.severity import Severity


@dataclass(frozen=True, kw_only=True, slots=True)
class ClosedSlice:
    repo: str
    slice_id: str
    name: str
    state: RunState
    run: Run
    spends: tuple[HarnessSpend, ...] = field(default=())
    findings: tuple[Finding, ...] = field(default=())
    discard_cause: DiscardCause | None = None

    @property
    def spend(self) -> HarnessSpend:
        return reduce(HarnessSpend.plus, self.spends, HarnessSpend.nothing())

    def count_findings(self, severity: Severity) -> int:
        return sum(1 for finding in self.findings if finding.severity is severity)
