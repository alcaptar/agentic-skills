from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar


class JudgeVerdictMother:
    @staticmethod
    def passing() -> dict[str, object]:
        return {"veredicto": "PASA", "hallazgos": []}

    @staticmethod
    def failing(*findings: dict[str, object]) -> dict[str, object]:
        return {"veredicto": "FALLA", "hallazgos": list(findings) or [JudgeVerdictMother.high_severity_finding()]}

    @staticmethod
    def passing_with(*findings: dict[str, object]) -> dict[str, object]:
        return {"veredicto": "PASA", "hallazgos": list(findings)}

    @staticmethod
    def high_severity_finding(*, path: str = "src/x.py") -> dict[str, object]:
        return {
            "regla": "boundaries",
            "path": path,
            "severidad": "alta",
            "evidencia": "requests in the domain",
            "detalle": "I/O goes behind a port",
        }


class HarnessEnvelopeMother:
    RECORDED: ClassVar[tuple[str, ...]] = ("full-recipe", "unbounded-tools")

    _DIRECTORY: ClassVar[Path] = Path(__file__).resolve().parents[1] / "payloads"

    @classmethod
    def recorded(cls, name: str = "full-recipe") -> dict[str, object]:
        data = json.loads((cls._DIRECTORY / f"{name}.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError(f"the recorded payload {name} is not an object")
        return data

    @classmethod
    def carrying(cls, verdict: dict[str, object], *, recorded: str = "full-recipe") -> dict[str, object]:
        return cls.recorded(recorded) | {"structured_output": verdict}

    @classmethod
    def plus(cls, **keys: object) -> dict[str, object]:
        return cls.recorded() | keys

    @classmethod
    def without(cls, key: str) -> dict[str, object]:
        return {name: value for name, value in cls.recorded().items() if name != key}
