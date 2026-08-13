from __future__ import annotations

import json
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import UnreadableForumError
from slice_runner.domain.forum import Forum
from slice_runner.infrastructure.gh_pull_request_payload import GhPullRequestPayload, GhPullRequestStatePayload
from slice_runner.infrastructure.gh_run_repository import GhCommandFailedError

if TYPE_CHECKING:
    from slice_runner.domain.pull_request_state import PullRequestState
    from slice_runner.infrastructure.gh_call import GhCall


class GhForum(Forum):
    def __init__(self, *, call: GhCall) -> None:
        self._call = call

    def open_pull_request(self, *, repo: str, branch: str) -> int | None:
        return self._listed(repo=repo, branch=branch, state="open")

    def any_pull_request(self, *, repo: str, branch: str) -> int | None:
        return self._listed(repo=repo, branch=branch, state="all")

    def _listed(self, *, repo: str, branch: str, state: str) -> int | None:
        argv = ["gh", "pr", "list", "--repo", repo, "--head", branch, "--state", state, "--json", "number"]
        outcome = self._call.run(argv, stdin="", safe_to_repeat=True)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {outcome.reason}")

        items = self._decoded_array(outcome.output.stdout)
        if not items:
            return None

        return GhPullRequestPayload.from_dict(items[0]).number

    def create_pull_request(self, *, repo: str, branch: str, base: str, title: str, body: str) -> int:
        argv = [
            "gh",
            "pr",
            "create",
            "--repo",
            repo,
            "--draft",
            "--base",
            base,
            "--head",
            branch,
            "--title",
            title,
            "--body-file",
            "-",
        ]
        outcome = self._call.run(argv, stdin=body, safe_to_repeat=False)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {outcome.reason}")

        return self._number_of(outcome.output.stdout)

    def pull_request_state(self, *, repo: str, number: int) -> PullRequestState:
        argv = ["gh", "pr", "view", str(number), "--repo", repo, "--json", "state"]
        outcome = self._call.run(argv, stdin="", safe_to_repeat=True)
        if outcome.output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {outcome.reason}")

        return GhPullRequestStatePayload.from_dict(self._decoded_object(outcome.output.stdout)).to_domain()

    def authenticated_as(self) -> str | None:
        outcome = self._call.run(["gh", "api", "user", "--jq", ".login"], stdin="", safe_to_repeat=True)
        if outcome.output.code != 0:
            return None

        return outcome.output.stdout.strip() or None

    def can_read(self, *, repo: str) -> bool:
        outcome = self._call.run(["gh", "repo", "view", repo, "--json", "name"], stdin="", safe_to_repeat=True)

        return outcome.output.code == 0

    @staticmethod
    def _number_of(stdout: str) -> int:
        url = stdout.strip()
        try:
            return int(url.rsplit("/", maxsplit=1)[-1])
        except ValueError as error:
            raise UnreadableForumError(f"gh did not print the url of the pull request it created: {url!r}") from error

    @classmethod
    def _decoded_array(cls, stdout: str) -> list[dict[str, object]]:
        data = cls._decoded(stdout)
        if not isinstance(data, list):
            raise UnreadableForumError(f"gh has to return an array, not {type(data).__name__}")

        return data

    @classmethod
    def _decoded_object(cls, stdout: str) -> dict[str, object]:
        data = cls._decoded(stdout)
        if not isinstance(data, dict):
            raise UnreadableForumError(f"gh has to return an object, not {type(data).__name__}")

        return data

    @staticmethod
    def _decoded(stdout: str) -> object:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as error:
            raise UnreadableForumError(f"gh did not return JSON: {error}") from error
