from __future__ import annotations

import subprocess

from slice_runner.infrastructure.process import Process, ProcessNotRunnableError, ProcessOutput


class LocalProcess(Process):
    def run(self, argv: list[str], *, stdin: str) -> ProcessOutput:
        try:
            finished = subprocess.run(argv, input=stdin, capture_output=True, text=True, check=False)
        except OSError as error:
            raise ProcessNotRunnableError(f"{argv[0]}: {error.strerror or error}") from error

        return ProcessOutput(code=finished.returncode, stdout=finished.stdout, stderr=finished.stderr)
