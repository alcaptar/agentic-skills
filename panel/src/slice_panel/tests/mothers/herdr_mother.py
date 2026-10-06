from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from slice_panel.tests.mothers.outcome_mother import OutcomeMother

if TYPE_CHECKING:
    from slice_panel.infrastructure.process_outcome import ProcessOutcome


class HerdrMother:
    TAB: ClassVar[str] = "w1:t2"
    PANE: ClassVar[str] = "w1:p3"

    @classmethod
    def tab_created(cls) -> ProcessOutcome:
        body = {
            "id": "cli:tab:create",
            "result": {
                "tab": {"tab_id": cls.TAB, "workspace_id": "w1", "label": "slice-05"},
                "root_pane": {"pane_id": cls.PANE, "tab_id": cls.TAB},
                "type": "tab_created",
            },
        }

        return OutcomeMother.succeeded(json.dumps(body))

    @classmethod
    def tab_created_without_the_pane(cls) -> ProcessOutcome:
        body = {"id": "cli:tab:create", "result": {"tab": {"tab_id": cls.TAB}, "type": "tab_created"}}

        return OutcomeMother.succeeded(json.dumps(body))
