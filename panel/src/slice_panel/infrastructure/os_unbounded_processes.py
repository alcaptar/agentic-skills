from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING, NoReturn

from slice_panel.infrastructure.unbounded_processes import UnboundedProcesses

if TYPE_CHECKING:
    from collections.abc import Sequence


class OsUnboundedProcesses(UnboundedProcesses):
    def spawned_detached(self, argv: Sequence[str]) -> None:
        subprocess.Popen(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def replaced_by(self, argv: Sequence[str]) -> NoReturn:
        os.execvp(argv[0], list(argv))
