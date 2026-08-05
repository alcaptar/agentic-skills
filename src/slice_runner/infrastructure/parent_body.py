from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from slice_runner.domain.control_command import ControlCommand
from slice_runner.domain.exceptions import MalformedConventionLineError
from slice_runner.domain.source import Source, SourceKind

if TYPE_CHECKING:
    from collections.abc import Iterator

_INTENTION_HEADING = re.compile(r"^\s*##\s+intenci[oó]n\s*$", re.IGNORECASE)
_SOURCES_HEADING = re.compile(r"^\s*##\s+fuentes\s+de\s+convenci[oó]n\s*$", re.IGNORECASE)
_CONTROLS_HEADING = re.compile(r"^\s*##\s+controles\s*$", re.IGNORECASE)
_H2 = re.compile(r"^\s*##\s+")
_SUBHEADING = re.compile(r"^\s*###\s+(.+?)\s*$")
_SOURCE_LINE = re.compile(r"^\s*-\s*(doc|skill)\s*:\s*(.+?)\s*$", re.IGNORECASE)
_CONTROL_LINE = re.compile(r"^\s*-\s*([\w-]+)\s*:\s*(.+?)\s*$")


@dataclass(frozen=True, kw_only=True, slots=True)
class ParsedParentBody:
    intention: str
    sources: tuple[Source, ...]
    controls: tuple[ControlCommand, ...]


class ParentBody:
    @classmethod
    def parse(cls, body: str, *, repo: str | None) -> ParsedParentBody:
        return ParsedParentBody(
            intention=cls._section_text(body, _INTENTION_HEADING),
            sources=cls._sources(body, repo),
            controls=cls._controls(body, repo),
        )

    @staticmethod
    def _section_text(body: str, heading: re.Pattern[str]) -> str:
        collected: list[str] = []
        in_section = False
        for line in body.splitlines():
            if heading.match(line):
                in_section = True
                continue
            if in_section:
                if _H2.match(line):
                    break
                collected.append(line)

        return "\n".join(collected).strip()

    @classmethod
    def _sources(cls, body: str, repo: str | None) -> tuple[Source, ...]:
        sources: list[Source] = []
        for owner, line in cls._repo_scoped_lines(body, _SOURCES_HEADING):
            if owner != repo:
                continue
            if m := _SOURCE_LINE.match(line):
                sources.append(Source(kind=SourceKind(m.group(1).lower()), path=m.group(2).strip()))
            elif cls._looks_like_an_item(line):
                raise MalformedConventionLineError(
                    f"a line under `## Fuentes de convencion` looks like a source but cannot be read as one: {line!r}"
                )

        return tuple(sources)

    @classmethod
    def _controls(cls, body: str, repo: str | None) -> tuple[ControlCommand, ...]:
        controls: list[ControlCommand] = []
        for owner, line in cls._repo_scoped_lines(body, _CONTROLS_HEADING):
            if owner != repo:
                continue
            if m := _CONTROL_LINE.match(line):
                controls.append(ControlCommand(name=m.group(1).strip(), command=m.group(2).strip()))
            elif cls._looks_like_an_item(line):
                raise MalformedConventionLineError(
                    f"a line under `## Controles` looks like a control but cannot be read as one: {line!r}"
                )

        return tuple(controls)

    @staticmethod
    def _looks_like_an_item(line: str) -> bool:
        return line.strip().startswith("-")

    @staticmethod
    def _repo_scoped_lines(body: str, heading: re.Pattern[str]) -> Iterator[tuple[str | None, str]]:
        in_section = False
        owner: str | None = None
        for line in body.splitlines():
            if heading.match(line):
                in_section = True
                owner = None
                continue
            if not in_section:
                continue
            if _H2.match(line):
                break
            if sub := _SUBHEADING.match(line):
                owner = sub.group(1)
                continue
            yield owner, line
