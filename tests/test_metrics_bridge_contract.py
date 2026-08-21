"""The last bridge between the program and `metrics.py`.

The program writes the durable log itself, in plain Python and without shelling out to this
script (`LocalMetricsLog`, `docs/conventions/infrastructure.md`), but the two still speak the
same vocabulary on purpose -- `DurableVerdict`/`DurableCi`/`DurableDiscardCause` on the program's
side, `Veredicto`/`Ci`/`CausaDescarte` on the script's -- because `metrics.py` is the only reader
of the rows the program writes. The first test measures that declared duplication directly; the
second passes what the program actually writes through the script's own reader, `Fila.from_row`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import metrics
from slice_runner.domain.ci_indeterminate_cause import CiIndeterminateCause
from slice_runner.domain.role_models import RoleModels
from slice_runner.domain.step import Step
from slice_runner.infrastructure.metrics_entry_payload import (
    DurableCi,
    DurableCiIndeterminateCause,
    DurableDiscardCause,
    DurableVerdict,
    MetricsEntryPayload,
)
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother
from slice_runner.tests.mothers.discarded_call_mother import DiscardedCallMother
from slice_runner.tests.mothers.harness_spend_mother import HarnessSpendMother


def test_the_durable_vocabulary_the_program_writes_is_the_one_metrics_py_reads() -> None:
    """The program writes the durable log itself, so both sides still spell the vocabulary.

    That duplication is the declared decision of `docs/conventions/infrastructure.md` -- the
    program imports nothing from `skills/` -- and a declared duplication that nobody measures is
    drift with a docstring. Adding a member on one side only turns the closing step of a run into a
    row `report` cannot classify, at the exact moment a failure loses the row outright.
    """
    duplicated = {
        "veredicto": ({str(v) for v in DurableVerdict}, {str(v) for v in metrics.Veredicto}),
        "ci": ({str(c) for c in DurableCi}, {str(c) for c in metrics.Ci}),
        "descartes_causa": (
            {str(c) for c in DurableDiscardCause},
            {str(c) for c in metrics.CausaDescarte},
        ),
        "ci_indeterminada_causa": (
            {str(c) for c in DurableCiIndeterminateCause},
            {str(c) for c in metrics.CausaCiIndeterminada},
        ),
    }

    for field, (program, script) in duplicated.items():
        assert program == script, (
            f"the program and metrics.py disagree on the `{field}` of the durable log: "
            f"only in the program {sorted(program - script)}, only in the script {sorted(script - program)}"
        )


def test_the_row_the_program_writes_is_one_metrics_py_can_still_read() -> None:
    """The row travels as a dict, so a rename on either side only shows up when a slice closes."""
    closed = ClosedSliceMother.merged_measuring(
        HarnessSpendMother.of_the_implementer_call(), HarnessSpendMother.of_the_judge_call()
    )
    row = MetricsEntryPayload.from_domain(closed, ts=datetime(2026, 8, 10, tzinfo=UTC).isoformat()).to_contract()

    fila = metrics.Fila.from_row(row)

    assert (fila.repo, fila.slice_id) == (closed.repo, closed.slice_id)
    assert (fila.veredicto, fila.ci) == (str(DurableVerdict.PASS), str(DurableCi.GREEN))
    assert (fila.coste_usd, fila.turnos, fila.duracion_ms, fila.tokens_cache) == (
        closed.spend.cost_usd,
        closed.spend.turns,
        closed.spend.duration_ms,
        closed.spend.cache_read_tokens,
    )
    assert fila.modelos == tuple(sorted(closed.spend.models))
    assert fila.variante == MetricsEntryPayload.VARIANT
    assert fila.primer_intento


def test_the_model_the_judge_ran_with_reaches_the_row_so_a_verdict_can_be_traced_to_what_measured_it() -> None:
    models = RoleModels(understand="sonnet", implement="sonnet", verify="opus")
    closed = ClosedSliceMother.merged_with_config(models=models)
    row = MetricsEntryPayload.from_domain(closed, ts=datetime(2026, 8, 10, tzinfo=UTC).isoformat()).to_contract()

    assert row["models_by_role"] == {"understand": "sonnet", "implement": "sonnet", "verify": "opus"}


def test_a_row_that_discards_the_judge_is_read_with_the_cause_metrics_py_knows() -> None:
    closed = ClosedSliceMother.merged_discarding_because_of(DiscardedCallMother.of_a_failed_call())
    row = MetricsEntryPayload.from_domain(closed, ts=datetime(2026, 8, 10, tzinfo=UTC).isoformat()).to_contract()

    fila = metrics.Fila.from_row(row)

    assert fila.descartes_verify_causa == metrics.CausaDescarte.LLAMADA_FALLIDA


def test_a_row_that_discards_a_step_other_than_verify_does_not_count_as_a_verify_discard() -> None:
    closed = ClosedSliceMother.merged_discarding_because_of(DiscardedCallMother.of_the_step(Step.UNDERSTAND))
    row = MetricsEntryPayload.from_domain(closed, ts=datetime(2026, 8, 10, tzinfo=UTC).isoformat()).to_contract()

    fila = metrics.Fila.from_row(row)

    assert fila.descartes_verify_causa is None


def test_a_row_that_closes_ci_indeterminate_is_read_with_the_cause_metrics_py_knows() -> None:
    closed = ClosedSliceMother.blocked_indeterminate_because_of(CiIndeterminateCause.COMMAND_FAILED)
    row = MetricsEntryPayload.from_domain(closed, ts=datetime(2026, 8, 10, tzinfo=UTC).isoformat()).to_contract()

    fila = metrics.Fila.from_row(row)

    assert fila.ci_indeterminada_causa == metrics.CausaCiIndeterminada.COMANDO_FALLIDO
