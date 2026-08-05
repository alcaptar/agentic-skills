from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.exceptions import EmptyIssueBodyError, UnreadableRunError
from slice_runner.infrastructure.run_payload import RunPayload

if TYPE_CHECKING:
    from slice_runner.domain.run import Run

_REPO_LINE = re.compile(r"^REPO\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_STATE_BLOCK = re.compile(r"<!-- slice-runner:estado\n(.*?)\n-->", re.DOTALL)


@dataclass(frozen=True, kw_only=True, slots=True)
class ParsedSubissueBody:
    repo: str | None
    run: Run | None


class SubissueBody:
    @classmethod
    def parse(cls, body: str) -> ParsedSubissueBody:
        return ParsedSubissueBody(repo=cls._repo(body), run=cls._run(body))

    @classmethod
    def with_run(cls, body: str, run: Run) -> str:
        if not body.strip():
            raise EmptyIssueBodyError("the issue body came back empty: there is no prose to derive a write from")

        block = cls._render_block(run)
        if _STATE_BLOCK.search(body):
            return _STATE_BLOCK.sub(lambda _: block, body, count=1)

        prose = body.rstrip("\n")

        return f"{prose}\n\n{block}\n"

    @staticmethod
    def _repo(body: str) -> str | None:
        found = _REPO_LINE.search(body)

        return found.group(1) if found else None

    @staticmethod
    def _run(body: str) -> Run | None:
        found = _STATE_BLOCK.search(body)
        if not found:
            return None

        try:
            data = json.loads(found.group(1))
        except json.JSONDecodeError as error:
            raise UnreadableRunError(f"the execution state block is not valid JSON: {error}") from error
        if not isinstance(data, dict):
            raise UnreadableRunError(f"the execution state block has to be an object, not {type(data).__name__}")

        return RunPayload.from_dict(data).to_domain()

    @staticmethod
    def _render_block(run: Run) -> str:
        payload = json.dumps(RunPayload.from_domain(run).to_contract(), ensure_ascii=False)

        return f"<!-- slice-runner:estado\n{payload}\n-->"
