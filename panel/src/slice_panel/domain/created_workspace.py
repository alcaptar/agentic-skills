from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class CreatedWorkspace:
    workspace_id: str
    root_pane: str
