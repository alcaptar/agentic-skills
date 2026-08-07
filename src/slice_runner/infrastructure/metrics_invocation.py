from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.domain.exceptions import RunNotClosedError
from slice_runner.domain.run_state import RunState
from slice_runner.domain.severity import Severity

if TYPE_CHECKING:
    from slice_runner.domain.closed_slice import ClosedSlice


class DurableVerdict(StrEnum):
    PASS = "PASA"
    FAIL = "FALLA"
    BLOCKED_CONTROLS = "bloqueada-controles"
    ABORTED_BUDGET = "abortada-presupuesto"


class DurableCi(StrEnum):
    GREEN = "green"
    RED = "red"
    NONE = "none"


class DurableDiscardCause(StrEnum):
    INCOHERENT_VERDICT = "veredicto-incoherente"
    FAILED_CALL = "llamada-fallida"

    @classmethod
    def of(cls, cause: DiscardCause) -> DurableDiscardCause:
        match cause:
            case DiscardCause.INCOHERENT_VERDICT:
                return cls.INCOHERENT_VERDICT
            case DiscardCause.FAILED_CALL:
                return cls.FAILED_CALL


@dataclass(frozen=True, kw_only=True, slots=True)
class DurableClosure:
    verdict: DurableVerdict
    ci: DurableCi

    @classmethod
    def of(cls, state: RunState) -> DurableClosure:
        match state:
            case RunState.MERGED:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.GREEN)
            case RunState.BLOCKED_CI_RED:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.RED)
            case RunState.BLOCKED_CI_INDETERMINATE:
                return cls(verdict=DurableVerdict.PASS, ci=DurableCi.NONE)
            case RunState.BLOCKED_VERIFY:
                return cls(verdict=DurableVerdict.FAIL, ci=DurableCi.NONE)
            case RunState.BLOCKED_CONTROLS:
                return cls(verdict=DurableVerdict.BLOCKED_CONTROLS, ci=DurableCi.NONE)
            case RunState.ABORTED_BUDGET:
                return cls(verdict=DurableVerdict.ABORTED_BUDGET, ci=DurableCi.NONE)
            case RunState.OPEN:
                raise RunNotClosedError(
                    f"a run in state {RunState.OPEN} has no verdict to record: "
                    f"the durable log is one line per closed slice"
                )


@dataclass(frozen=True, kw_only=True, slots=True)
class MetricsInvocation:
    EXECUTABLE: ClassVar[str] = "python3"
    PROGRAM_ROOT: ClassVar[Path] = Path(__file__).parents[3]
    SCRIPT: ClassVar[tuple[str, ...]] = ("skills", "slice-runner", "scripts", "metrics.py")

    closed: ClosedSlice

    @property
    def script(self) -> Path:
        return self.PROGRAM_ROOT.joinpath(*self.SCRIPT)

    @property
    def argv(self) -> list[str]:
        closure = DurableClosure.of(self.closed.state)
        run = self.closed.run

        return [
            self.EXECUTABLE,
            str(self.script),
            "record",
            "--repo",
            self.closed.repo,
            "--slice",
            self.closed.slice_id,
            "--name",
            self.closed.name,
            "--veredicto",
            closure.verdict.value,
            "--ci",
            closure.ci.value,
            "--hallazgos-alta",
            str(self.closed.count_findings(Severity.HIGH)),
            "--hallazgos-media",
            str(self.closed.count_findings(Severity.MEDIUM)),
            "--hallazgos-baja",
            str(self.closed.count_findings(Severity.LOW)),
            "--hallazgos-ronda-final-alta",
            str(self.closed.count_findings_of_the_last_round(Severity.HIGH)),
            "--hallazgos-ronda-final-media",
            str(self.closed.count_findings_of_the_last_round(Severity.MEDIUM)),
            "--hallazgos-ronda-final-baja",
            str(self.closed.count_findings_of_the_last_round(Severity.LOW)),
            "--reintentos-implement",
            str(run.implement_retries),
            "--reintentos-controles",
            str(run.control_retries),
            "--reintentos-verify",
            str(run.verify_retries),
            "--reintentos-ci",
            str(run.ci_retries),
            "--descartes-verify",
            str(run.verify_discards),
            *self._cause_of_the_discards,
            *self._what_the_harness_measured,
        ]

    @property
    def _cause_of_the_discards(self) -> list[str]:
        cause = self.closed.discard_cause

        return ["--descartes-verify-causa", DurableDiscardCause.of(cause).value] if cause else []

    @property
    def _what_the_harness_measured(self) -> list[str]:
        spend = self.closed.spend
        if not spend.measured:
            return []

        return [
            "--coste-usd",
            str(spend.cost_usd),
            "--turnos",
            str(spend.turns),
            "--duracion-ms",
            str(spend.duration_ms),
        ]
