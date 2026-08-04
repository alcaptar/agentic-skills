from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slice_runner.domain.diff_on_disk import DiffOnDisk


class JudgePrompt:
    def __init__(self, *, system_template: str, repo: str, diff: DiffOnDisk) -> None:
        self._system_template = system_template
        self._repo = repo
        self._diff = diff

    @property
    def repo(self) -> str:
        return self._repo

    @property
    def diff(self) -> DiffOnDisk:
        return self._diff

    def build(self) -> str:
        return "\n".join(
            [
                self._system_template,
                "",
                "## Datos del run",
                "",
                f"- ruta del repo: {self._repo}",
                f"- `slice.diff`: {self._diff.diff}",
                f"- ficheros que toca la slice ({len(self._diff.files)}):",
                *(f"  - {path}" for path in self._diff.files),
            ]
        )
