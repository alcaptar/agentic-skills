from __future__ import annotations

from typing import ClassVar

from slice_runner.domain.control_command import ControlCommand


class ControlCommandMother:
    LINT_NAME: ClassVar[str] = "lint"
    LINT_COMMAND: ClassVar[str] = "make linting"

    @classmethod
    def lint(cls) -> ControlCommand:
        return ControlCommand(name=cls.LINT_NAME, command=cls.LINT_COMMAND)
