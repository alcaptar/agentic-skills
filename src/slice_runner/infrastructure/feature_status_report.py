from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.slice_status import SliceStatus


@dataclass(frozen=True, kw_only=True, slots=True)
class FeatureStatusReport:
    statuses: tuple[SliceStatus, ...]

    def rendered(self) -> str:
        return "\n".join(self._line(status) for status in self.statuses)

    def _line(self, status: SliceStatus) -> str:
        parts = [f"{status.sub_issue.slice_id.canonical:<10}", f"{self._label(status):<28}"]
        run = status.sub_issue.run
        if run is not None:
            parts.append(run.step.value)
            if run.spend.measured:
                parts.append(f"${run.spend.cost_usd:.2f}")
            if run.implement_retries > 0:
                parts.append(f"retries={run.implement_retries}")
        if status.pull_request is not None:
            parts.append(f"#{status.pull_request}")

        return " ".join(parts)

    @staticmethod
    def _label(status: SliceStatus) -> str:
        if status.sub_issue.label is not None:
            return status.sub_issue.label.value

        return status.sub_issue.state.value
