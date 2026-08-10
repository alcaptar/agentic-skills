"""The last bridge between the program and `metrics.py`.

`docs/conventions/infrastructure.md` declares that the program shells out to `metrics.py` instead
of importing it -- the program does not import anything from `skills/` -- so the durable
vocabulary it writes and the record it invokes the script with are stated twice on purpose. Both
tests here measure that declared duplication: one compares the two closed vocabularies directly,
the other passes the argv the program builds through the script's own `argparse`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import metrics
from slice_runner.domain.discard_cause import DiscardCause
from slice_runner.infrastructure.metrics_invocation import (
    DurableCi,
    DurableDiscardCause,
    DurableVerdict,
    MetricsInvocation,
)
from slice_runner.tests.mothers.closed_slice_mother import ClosedSliceMother

if TYPE_CHECKING:
    from pathlib import Path


def test_the_durable_vocabulary_the_program_writes_is_the_one_the_metrics_cli_accepts() -> None:
    """The program shells out to `metrics.py` instead of importing it, so both spell the vocabulary.

    That duplication is the declared decision of `docs/conventions/infrastructure.md` -- the program
    imports nothing from `skills/` -- and a declared duplication that nobody measures is drift with a
    docstring. Adding a member on one side only turns the closing step of a run into an argparse
    error, at the exact moment a failure loses the row outright.
    """
    duplicated = {
        "veredicto": ({str(v) for v in DurableVerdict}, {str(v) for v in metrics.Veredicto}),
        "ci": ({str(c) for c in DurableCi}, {str(c) for c in metrics.Ci}),
        "descartes_verify_causa": (
            {str(c) for c in DurableDiscardCause},
            {str(c) for c in metrics.CausaDescarte},
        ),
    }

    for field, (program, script) in duplicated.items():
        assert program == script, (
            f"the program and metrics.py disagree on the `{field}` of the durable log: "
            f"only in the program {sorted(program - script)}, only in the script {sorted(script - program)}"
        )


def test_the_record_the_program_builds_is_one_the_metrics_cli_accepts(tmp_path: Path) -> None:
    """The flags travel as an argv, so a rename on either side only shows up when a slice closes.

    The first two entries of the invocation are the interpreter and the resolved path of the script,
    which is what a subprocess needs and what `main` must not see; `--path` goes last so the assert
    reads a throwaway log instead of the real durable one.
    """
    closed = ClosedSliceMother.merged_discarding_because_of(DiscardCause.FAILED_CALL)
    log = tmp_path / "metrics.jsonl"

    assert metrics.main([*MetricsInvocation(closed=closed).argv[2:], "--path", str(log)]) == 0

    row = json.loads(log.read_text(encoding="utf-8").strip())
    assert row["harness"] == {
        "coste_usd": closed.spend.cost_usd,
        "turnos": closed.spend.turns,
        "duracion_ms": closed.spend.duration_ms,
        "tokens_cache": closed.spend.cache_read_tokens,
    }
    assert row["modelos"] == list(closed.spend.models)
    assert row["variante"] == MetricsInvocation.VARIANT
    assert row["descartes_verify_causa"] == str(DurableDiscardCause.FAILED_CALL)
