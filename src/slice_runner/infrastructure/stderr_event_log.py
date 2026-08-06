from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from slice_runner.domain.event_log import EventLog
from slice_runner.infrastructure.event_payload import EventPayload

if TYPE_CHECKING:
    from slice_runner.domain.event import Event


class StderrEventLog(EventLog):
    def emit(self, event: Event) -> None:
        print(json.dumps(EventPayload.from_domain(event).to_contract(), ensure_ascii=False), file=sys.stderr)
