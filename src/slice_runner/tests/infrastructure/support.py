from __future__ import annotations

import json
from pathlib import Path

from slice_runner.infrastructure.process import Process, ProcessNotRunnableError, ProcessOutput
from slice_runner.tests.git_repo import git, init_repo

_PAYLOADS = Path(__file__).parent / "payloads"

RECORDED = ("full-recipe", "unbounded-tools")


def payload(name: str) -> dict[str, object]:
    data = json.loads((_PAYLOADS / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def with_verdict(structure: dict[str, object], *, recorded: str = "full-recipe") -> dict[str, object]:
    return dict(payload(recorded)) | {"structured_output": structure}


class RecordedProcess(Process):
    def __init__(self, output: dict[str, object], *, code: int = 0) -> None:
        self._output = output
        self._code = code
        self.argv: list[str] = []
        self.stdin = ""
        self.calls = 0

    def run(self, argv: list[str], *, stdin: str) -> ProcessOutput:
        self.argv = argv
        self.stdin = stdin
        self.calls += 1
        return ProcessOutput(code=self._code, stdout=json.dumps(self._output), stderr="")


class UnrunnableProcess(Process):
    def run(self, argv: list[str], *, stdin: str) -> ProcessOutput:
        raise ProcessNotRunnableError(f"{argv[0]}: no such executable")


def repo_with_the_slice_staged(root: Path) -> Path:
    repo = init_repo(root / "repo")
    (repo / "mod.py").write_text("def f() -> int:\n    return 1\n", encoding="utf-8")
    git(repo, "add", "mod.py")
    git(repo, "commit", "-m", "base")
    git(repo, "switch", "-c", "slice/01-x")
    (repo / "mod.py").write_text("def f() -> int:\n    return 2\n", encoding="utf-8")
    git(repo, "add", "mod.py")
    return repo


def repo_with_nothing_staged(root: Path) -> Path:
    repo = repo_with_the_slice_staged(root)
    git(repo, "reset", "--hard")
    return repo
