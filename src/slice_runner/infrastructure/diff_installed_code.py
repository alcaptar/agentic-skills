from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import UnreadableProvenanceError
from slice_runner.domain.installed_code import InstalledCode
from slice_runner.domain.installed_code_match import InstalledCodeMatch
from slice_runner.infrastructure.process import ProcessNotRunnableError, ProcessTimedOutError
from slice_runner.infrastructure.uv_tool_installation import UvToolInstallation

if TYPE_CHECKING:
    from pathlib import Path

    from slice_runner.infrastructure.process import Process


class DiffInstalledCode(InstalledCode):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def compared_with(self, *, checkout: Path) -> InstalledCodeMatch:
        if not checkout.is_dir():
            return InstalledCodeMatch.CHECKOUT_GONE

        installed = UvToolInstallation().installed_package()
        argv = ["diff", "-rq", "-x", "__pycache__", str(installed), str(checkout / "src" / UvToolInstallation.PACKAGE)]
        try:
            output = self._process.run(argv, stdin="")
        except (ProcessTimedOutError, ProcessNotRunnableError) as error:
            raise UnreadableProvenanceError(f"{' '.join(argv)}: {error}") from error
        if output.code == 0:
            return InstalledCodeMatch.SAME
        if output.code == 1:
            return InstalledCodeMatch.DIFFERENT

        raise UnreadableProvenanceError(output.reason(tool=argv[0]))
