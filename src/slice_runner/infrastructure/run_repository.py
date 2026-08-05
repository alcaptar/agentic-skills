from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import LaggingSearchIndexError, UnreadableIssueError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.parent_issue import ParentIssue
from slice_runner.domain.sub_issue import SubIssue
from slice_runner.infrastructure.gh_body_payload import GhBodyPayload
from slice_runner.infrastructure.gh_parent_view_payload import GhParentViewPayload
from slice_runner.infrastructure.gh_sub_issue_payload import GhSubIssuePayload
from slice_runner.infrastructure.parent_body import ParentBody
from slice_runner.infrastructure.subissue_body import SubissueBody

if TYPE_CHECKING:
    from slice_runner.domain.run import Run
    from slice_runner.infrastructure.gh_sub_issue_payload import GhLabelPayload
    from slice_runner.infrastructure.process import Process, ProcessOutput

_SLICE_ID = re.compile(r"^(slice-\d+)")
_LABEL_MISSING = re.compile(r"'(.+?)' not found")
_LABEL_COLOR = "5319e7"
_LABEL_DESCRIPTION = "estado de una slice, escrito por slice-runner"


class GhCommandFailedError(OSError):
    pass


class RunRepository:
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def read_parent(self, *, repo: str, issue: int, slice_repo: str | None) -> ParentIssue:
        output = self._run(["gh", "issue", "view", str(issue), "--repo", repo, "--json", "body,subIssuesSummary"])
        payload = GhParentViewPayload.from_dict(self._decoded_object(output))
        parsed = ParentBody.parse(payload.body, repo=slice_repo)

        return ParentIssue(
            intention=parsed.intention,
            sources=parsed.sources,
            controls=parsed.controls,
            subissue_count=payload.subissues_summary.total,
        )

    def read_children(self, *, repo: str, parent: int, expected: int) -> tuple[SubIssue, ...]:
        search = f"parent-issue:{repo}#{parent}"
        output = self._run(
            ["gh", "issue", "list", "--repo", repo, "--search", search, "--json", "number,title,body,labels"]
        )
        items = self._decoded_array(output)
        children = tuple(self._sub_issue_from(GhSubIssuePayload.from_dict(item)) for item in items)
        if len(children) < expected:
            raise LaggingSearchIndexError(
                f"the search index for {repo}#{parent} returned {len(children)} subissue(s), "
                f"the graph knows about {expected}"
            )

        return tuple(sorted(children, key=self._slice_number))

    def write_run(self, *, repo: str, issue: int, run: Run) -> None:
        current = GhBodyPayload.from_dict(
            self._decoded_object(self._run(["gh", "issue", "view", str(issue), "--repo", repo, "--json", "body"]))
        ).body
        updated = SubissueBody.with_run(current, run)
        if updated == current:
            return

        self._run(["gh", "issue", "edit", str(issue), "--repo", repo, "--body-file", "-"], stdin=updated)

    def write_label(self, *, repo: str, issue: int, remove: IssueLabel, add: IssueLabel) -> None:
        argv = [
            "gh",
            "issue",
            "edit",
            str(issue),
            "--repo",
            repo,
            "--add-label",
            add.value,
            "--remove-label",
            remove.value,
        ]
        output = self._process.run(argv, stdin="")
        if output.code == 0:
            return

        missing = _LABEL_MISSING.search(output.stderr)
        if not missing or missing.group(1) != add.value:
            raise GhCommandFailedError(f"gh issue edit failed for {repo}#{issue}: {output.stderr.strip()}")

        self._create_label(repo=repo, name=add.value)
        retried = self._process.run(argv, stdin="")
        if retried.code != 0:
            raise GhCommandFailedError(
                f"gh issue edit failed for {repo}#{issue} even after creating {add.value!r}: {retried.stderr.strip()}"
            )

    def _create_label(self, *, repo: str, name: str) -> None:
        output = self._process.run(
            [
                "gh",
                "label",
                "create",
                name,
                "--repo",
                repo,
                "--color",
                _LABEL_COLOR,
                "--description",
                _LABEL_DESCRIPTION,
            ],
            stdin="",
        )
        if output.code != 0:
            raise GhCommandFailedError(f"gh label create failed for {repo}/{name}: {output.stderr.strip()}")

    def _run(self, argv: list[str], *, stdin: str = "") -> ProcessOutput:
        output = self._process.run(argv, stdin=stdin)
        if output.code != 0:
            raise GhCommandFailedError(f"{' '.join(argv)}: {output.stderr.strip()}")

        return output

    @staticmethod
    def _decoded(output: ProcessOutput) -> object:
        try:
            return json.loads(output.stdout)
        except json.JSONDecodeError as error:
            raise UnreadableIssueError(f"gh did not return JSON: {error}") from error

    @classmethod
    def _decoded_object(cls, output: ProcessOutput) -> dict[str, object]:
        data = cls._decoded(output)
        if not isinstance(data, dict):
            raise UnreadableIssueError(f"gh has to return an object, not {type(data).__name__}")

        return data

    @classmethod
    def _decoded_array(cls, output: ProcessOutput) -> list[dict[str, object]]:
        data = cls._decoded(output)
        if not isinstance(data, list):
            raise UnreadableIssueError(f"gh has to return an array, not {type(data).__name__}")

        return data

    @classmethod
    def _sub_issue_from(cls, payload: GhSubIssuePayload) -> SubIssue:
        parsed = SubissueBody.parse(payload.body)

        return SubIssue(
            number=payload.number,
            slice_id=cls._slice_id_of(payload.title),
            title=payload.title,
            repo=parsed.repo,
            run=parsed.run,
            label=cls._label_of(payload.labels),
        )

    @staticmethod
    def _slice_id_of(title: str) -> str:
        matched = _SLICE_ID.match(title)
        if not matched:
            raise UnreadableIssueError(f"the subissue title does not start with `slice-NN`: {title!r}")

        return matched.group(1)

    @staticmethod
    def _label_of(labels: list[GhLabelPayload]) -> IssueLabel | None:
        known = set(IssueLabel)
        for label in labels:
            if label.name in known:
                return IssueLabel(label.name)

        return None

    @staticmethod
    def _slice_number(child: SubIssue) -> int:
        return int(child.slice_id.removeprefix("slice-"))
