from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.metrics_log import MetricsLog
from slice_runner.infrastructure.metrics_invocation import MetricsInvocation

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice
    from slice_runner.infrastructure.process import Process


class MetricsNotRecordedError(OSError):
    pass


class MetricsScriptLog(MetricsLog):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def record(self, closed: ClosedSlice) -> None:
        invocation = MetricsInvocation(closed=closed)
        output = self._process.run(invocation.argv, stdin="")
        if output.code != 0:
            raise MetricsNotRecordedError(
                f"{invocation.script} exited {output.code} and {closed.slice_id} went unmeasured: "
                f"{output.stderr.strip()}"
            )
