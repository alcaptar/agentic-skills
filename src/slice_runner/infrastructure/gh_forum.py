from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.domain.forum import Forum
from slice_runner.infrastructure.gh_pull_request_payload import GhPullRequestPayload
from slice_runner.infrastructure.run_repository import GhCommandFailedError

if TYPE_CHECKING:
    from slice_runner.infrastructure.process import Process


class GhForum(Forum):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def open_pull_request(self, *, repo: str, branch: str) -> int | None:
        argv = ["gh", "pr", "list", "--repo", repo, "--head", branch, "--state", "open", "--json", "number"]
        output = self._process.run(argv, stdin="")
        if output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {output.stderr.strip()}")

        items = self._decoded_array(output.stdout)
        if not items:
            return None

        return GhPullRequestPayload.from_dict(items[0]).number

    @staticmethod
    def _decoded_array(stdout: str) -> list[dict[str, object]]:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise UnreadableForumError(f"gh did not return JSON: {error}") from error
        if not isinstance(data, list):
            raise UnreadableForumError(f"gh has to return an array, not {type(data).__name__}")

        return data
