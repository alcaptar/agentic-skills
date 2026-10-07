from __future__ import annotations

from enum import StrEnum


class MountingStep(StrEnum):
    START_COORDINATOR = "start-coordinator"
    SPLIT_PANE = "split-pane"
    RUN_PANEL = "run-panel"
    FOCUS = "focus"
