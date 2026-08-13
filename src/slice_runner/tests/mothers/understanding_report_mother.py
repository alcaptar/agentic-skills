from __future__ import annotations

from typing import ClassVar


class UnderstandingReportMother:
    SUMMARY: ClassVar[str] = "hoy el entendimiento es un campo de texto libre; esta slice le da forma"
    STEP_DESCRIPTION: ClassVar[str] = "infrastructure/understanding_report_payload.py"
    STEP_REASON: ClassVar[str] = "todo lo demas depende de que campos y topes existen"
    SKETCH: ClassVar[str] = (
        "UnderstandingReportPayload(ContractModel): summary, steps y sketch como campos obligatorios"
    )

    @classmethod
    def valid(cls) -> dict[str, object]:
        return {
            "summary": cls.SUMMARY,
            "steps": [{"description": cls.STEP_DESCRIPTION, "reason": cls.STEP_REASON}],
            "sketch": cls.SKETCH,
        }

    @classmethod
    def without(cls, key: str) -> dict[str, object]:
        return {name: value for name, value in cls.valid().items() if name != key}

    @classmethod
    def with_a_step_missing_its_reason(cls) -> dict[str, object]:
        return cls.valid() | {"steps": [{"description": cls.STEP_DESCRIPTION}]}

    @classmethod
    def with_steps(cls, count: int) -> dict[str, object]:
        step = {"description": cls.STEP_DESCRIPTION, "reason": cls.STEP_REASON}

        return cls.valid() | {"steps": [step] * count}
