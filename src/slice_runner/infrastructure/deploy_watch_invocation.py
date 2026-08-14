from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True, slots=True)
class DeployWatchInvocation:
    EXECUTABLE: ClassVar[str] = "claude"
    TOOLS: ClassVar[tuple[str, ...]] = ("Read", "Grep", "Glob", "Skill", "Bash", "Agent")

    worktree: str
    repo: str
    signal: str

    @property
    def cwd(self) -> str:
        return self.worktree

    @property
    def argv(self) -> list[str]:
        return [
            self.EXECUTABLE,
            "-p",
            "--permission-mode",
            "bypassPermissions",
            "--tools",
            ",".join(self.TOOLS),
            "--strict-mcp-config",
            "--setting-sources",
            "user",
        ]

    @property
    def text(self) -> str:
        return f"/deploy-watch senal: {self.signal}; repo destino: {self.repo}"
