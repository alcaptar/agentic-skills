from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.exceptions import UnreadableFindingsError
from slice_runner.infrastructure.automation_mark import AutomationMark
from slice_runner.infrastructure.published_finding_payload import PublishedFindingPayload

if TYPE_CHECKING:
    from slice_runner.domain.finding import Finding


class VetoFindingsComment:
    MARKER: ClassVar[str] = "<!-- slice-runner:hallazgos -->"
    _BLOCK: ClassVar[re.Pattern[str]] = re.compile(r"<!-- slice-runner:hallazgos-json\n(.*?)\n-->", re.DOTALL)

    @classmethod
    def rendered(cls, findings: tuple[Finding, ...]) -> str:
        numbered = tuple(enumerate(findings, start=1))

        return "\n\n".join(
            [
                "\n".join(cls._line(index, finding) for index, finding in numbered),
                cls._block(numbered),
                cls.MARKER,
                AutomationMark.TEXT,
            ]
        )

    @classmethod
    def is_the_veto_findings(cls, body: str) -> bool:
        return cls.MARKER in body

    @classmethod
    def finding_of(cls, body: str, finding_id: str) -> Finding | None:
        for published in cls._decoded(body):
            if published.id == finding_id:
                return published.to_domain()

        return None

    @staticmethod
    def _line(index: int, finding: Finding) -> str:
        return f"- `f{index}` {finding.severity}: {finding.rule} - {finding.detail} ({finding.path})"

    @staticmethod
    def _block(numbered: tuple[tuple[int, Finding], ...]) -> str:
        payload = [
            PublishedFindingPayload.from_domain(id=f"f{index}", finding=finding).to_contract()
            for index, finding in numbered
        ]

        return f"<!-- slice-runner:hallazgos-json\n{json.dumps(payload, ensure_ascii=False)}\n-->"

    @classmethod
    def _decoded(cls, body: str) -> tuple[PublishedFindingPayload, ...]:
        found = cls._BLOCK.search(body)
        if not found:
            return ()

        try:
            data = json.loads(found.group(1))
        except json.JSONDecodeError as error:
            raise UnreadableFindingsError(f"the veto findings block is not valid JSON: {error}") from error
        if not isinstance(data, list):
            raise UnreadableFindingsError(f"the veto findings block has to be an array, not {type(data).__name__}")

        return tuple(PublishedFindingPayload.from_dict(item) for item in data)
