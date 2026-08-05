from __future__ import annotations

from pathlib import PurePosixPath
from typing import ClassVar

from slice_runner.domain.hygiene_breach import HygieneBreach
from slice_runner.domain.hygiene_offence import HygieneOffence


class StagedHygiene:
    FORBIDDEN_PREFIXES: ClassVar[tuple[str, ...]] = (
        "docs/superpowers/specs/",
        "docs/superpowers/plans/",
    )

    @classmethod
    def of(cls, *, staged: tuple[str, ...], declared: tuple[str, ...]) -> tuple[HygieneOffence, ...]:
        allowed = {cls._normalized(path) for path in declared}
        offences = (cls._offence(cls._normalized(path), allowed) for path in staged)

        return tuple(offence for offence in offences if offence is not None)

    @classmethod
    def _offence(cls, path: str, allowed: set[str]) -> HygieneOffence | None:
        if path.startswith(cls.FORBIDDEN_PREFIXES):
            return HygieneOffence(path=path, breach=HygieneBreach.FORBIDDEN_ARTIFACT)
        if path not in allowed:
            return HygieneOffence(path=path, breach=HygieneBreach.NOT_DECLARED)

        return None

    @staticmethod
    def _normalized(path: str) -> str:
        return PurePosixPath(path).as_posix()
