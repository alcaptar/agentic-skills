from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from slice_runner.domain.alignment_response import AlignmentResponse
from slice_runner.domain.exceptions import LaggingSearchIndexError, UnreadableIssueError
from slice_runner.domain.issue_label import IssueLabel
from slice_runner.domain.parent_issue import ParentIssue
from slice_runner.domain.run_repository import RunRepository
from slice_runner.domain.sub_issue import SubIssue
from slice_runner.infrastructure.gh_body_payload import GhBodyPayload
from slice_runner.infrastructure.gh_comments_payload import GhCommentPayload, GhCommentsPayload
from slice_runner.infrastructure.gh_parent_view_payload import GhParentViewPayload
from slice_runner.infrastructure.gh_sub_issue_payload import GhSubIssuePayload
from slice_runner.infrastructure.parent_body import ParentBody
from slice_runner.infrastructure.subissue_body import SubissueBody
from slice_runner.infrastructure.understanding_comment import UnderstandingComment

if TYPE_CHECKING:
    from slice_runner.domain.run import Run
    from slice_runner.infrastructure.gh_sub_issue_payload import GhLabelPayload
    from slice_runner.infrastructure.process import Process, ProcessOutput

_SLICE_HEADING = re.compile(r"^(slice-\d+)\s*\(([^)]+)\)\s*:\s*(.+?)\s*$")
_LABEL_MISSING = re.compile(r"'(.+?)' not found")
_LABEL_COLOR = "5319e7"
_LABEL_DESCRIPTION = "estado de una slice, escrito por slice-runner"


class GhCommandFailedError(OSError):
    pass


class GhRunRepository(RunRepository):
    def __init__(self, *, process: Process) -> None:
        self._process = process

    def read_parent(self, *, repo: str, issue: int, slice_repo: str | None) -> ParentIssue:
        output = self._run(["gh", "issue", "view", str(issue), "--repo", repo, "--json", "body,subIssuesSummary,state"])
        payload = GhParentViewPayload.from_dict(self._decoded_object(output))
        parsed = ParentBody.parse(payload.body, repo=slice_repo)

        return ParentIssue(
            intention=parsed.intention,
            sources=parsed.sources,
            controls=parsed.controls,
            subissue_count=payload.subissues_summary.total,
            state=payload.state,
        )

    def read_children(self, *, repo: str, parent: int, expected: int) -> tuple[SubIssue, ...]:
        search = f"parent-issue:{repo}#{parent}"
        output = self._run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repo,
                "--search",
                search,
                "--state",
                "all",
                "--json",
                "number,title,body,labels,state",
            ]
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

    def write_understanding(self, *, repo: str, issue: int, understanding: str) -> None:
        self._run(
            ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=UnderstandingComment.rendered(understanding),
        )

    def read_understanding(self, *, repo: str, issue: int) -> str:
        published = [
            body
            for body in self._comment_bodies(repo=repo, issue=issue)
            if UnderstandingComment.is_the_understanding(body)
        ]
        if not published:
            return ""

        return UnderstandingComment.written_in(published[-1])

    def read_alignment_response(self, *, repo: str, issue: int) -> AlignmentResponse:
        return AlignmentResponse.of_the_comments(
            self._after_the_understanding(self._comment_bodies(repo=repo, issue=issue))
        )

    def _comment_bodies(self, *, repo: str, issue: int) -> tuple[str, ...]:
        output = self._run(["gh", "issue", "view", str(issue), "--repo", repo, "--json", "comments"])
        payload = GhCommentsPayload.from_dict(self._decoded_object(output))

        return tuple(GhCommentPayload.from_dict(comment).body for comment in payload.comments)

    @staticmethod
    def _after_the_understanding(bodies: tuple[str, ...]) -> tuple[str, ...]:
        for index in range(len(bodies) - 1, -1, -1):
            if UnderstandingComment.is_the_understanding(bodies[index]):
                return bodies[index + 1 :]

        return ()

    def write_label(self, *, repo: str, issue: int, remove: IssueLabel | None, add: IssueLabel) -> None:
        argv = self._edit_of(repo=repo, issue=issue, add=add, remove=remove)
        self._edit_with_label_fallback(argv, repo=repo, issue=issue, add=add)

    def remove_label(self, *, repo: str, issue: int, remove: IssueLabel) -> None:
        self._run(["gh", "issue", "edit", str(issue), "--repo", repo, "--remove-label", remove.value])

    def pause_for_alignment(self, *, repo: str, issue: int, remove: IssueLabel | None) -> None:
        argv = [
            *self._edit_of(repo=repo, issue=issue, add=IssueLabel.AWAITING_ALIGNMENT, remove=remove),
            "--add-assignee",
            "@me",
        ]
        self._edit_with_label_fallback(argv, repo=repo, issue=issue, add=IssueLabel.AWAITING_ALIGNMENT)

    def flag_draft_pull_request(self, *, repo: str, issue: int, pull_request: int) -> None:
        self._run(
            ["gh", "issue", "comment", str(issue), "--repo", repo, "--body-file", "-"],
            stdin=(
                f"La pull request #{pull_request} nace en borrador (`--draft`); hay que sacarla de "
                "borrador para que el merge pueda ocurrir."
            ),
        )

    def close_parent(self, *, repo: str, issue: int, subissue_count: int) -> None:
        self._run(
            [
                "gh",
                "issue",
                "close",
                str(issue),
                "--repo",
                repo,
                "--comment",
                f"Las {subissue_count} subissue(s) de esta feature estan todas cerradas, asi que esta feature "
                "se cierra con ellas.",
            ]
        )

    @staticmethod
    def _edit_of(*, repo: str, issue: int, add: IssueLabel, remove: IssueLabel | None) -> list[str]:
        argv = ["gh", "issue", "edit", str(issue), "--repo", repo, "--add-label", add.value]
        if remove is None:
            return argv

        return [*argv, "--remove-label", remove.value]

    def _edit_with_label_fallback(self, argv: list[str], *, repo: str, issue: int, add: IssueLabel) -> None:
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
        heading = cls._heading_of(payload.title)

        return SubIssue(
            number=payload.number,
            slice_id=heading.group(1),
            name=heading.group(2),
            summary=heading.group(3),
            title=payload.title,
            state=payload.state,
            repo=parsed.repo,
            intention=parsed.intention,
            criteria=parsed.criteria,
            signal=parsed.signal,
            run=parsed.run,
            label=cls._label_of(payload.labels),
        )

    @staticmethod
    def _heading_of(title: str) -> re.Match[str]:
        matched = _SLICE_HEADING.match(title)
        if not matched:
            raise UnreadableIssueError(f"the subissue title does not open with `slice-NN (name):`: {title!r}")

        return matched

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
