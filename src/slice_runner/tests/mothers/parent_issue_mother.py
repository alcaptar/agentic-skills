from __future__ import annotations

from dataclasses import replace

from slice_runner.domain.control_command import ControlCommand
from slice_runner.domain.controls import Controls
from slice_runner.domain.parent_issue import ParentIssue
from slice_runner.domain.source import Source, SourceKind


class ParentIssueMother:
    @staticmethod
    def with_sources_and_controls() -> ParentIssue:
        return ParentIssue(
            intention="hoy nada evita reimplementar una slice ya entregada",
            sources=(Source(kind=SourceKind.DOC, path="CLAUDE.md"),),
            controls=Controls(commands=(ControlCommand(name="lint", command="make linting"),), exemption_reason=None),
            subissue_count=1,
        )

    @staticmethod
    def without_sources() -> ParentIssue:
        return replace(ParentIssueMother.with_sources_and_controls(), sources=())

    @staticmethod
    def without_controls() -> ParentIssue:
        return replace(
            ParentIssueMother.with_sources_and_controls(), controls=Controls(commands=(), exemption_reason=None)
        )

    @staticmethod
    def with_exempt_controls() -> ParentIssue:
        return replace(
            ParentIssueMother.with_sources_and_controls(),
            controls=Controls(commands=(), exemption_reason="la integracion continua solo publica en master"),
        )
