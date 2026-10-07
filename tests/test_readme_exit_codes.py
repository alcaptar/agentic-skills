from __future__ import annotations

import re
from typing import ClassVar

import pytest
from conftest import _ROOT, _read

from slice_runner.infrastructure.exit_code import ExitCode


class _ReadmeExitCodeRows:
    ALIGNMENT: ClassVar[re.Pattern[str]] = re.compile(r"alineaci", re.IGNORECASE)

    @staticmethod
    def row_of(code: ExitCode, table: str) -> str:
        rows = [line for line in table.splitlines() if line.startswith(f"| `{int(code)}` |")]
        assert len(rows) == 1, f"the exit code table must have exactly one row for {int(code)}"

        return rows[0]

    @classmethod
    def mentions_the_alignment(cls, row: str) -> bool:
        return cls.ALIGNMENT.search(row) is not None


class TestTheRowOfTheExhaustedWaitDescribesTheWaitsThatCanExhaust(_ReadmeExitCodeRows):
    def test_the_row_does_not_mention_the_alignment_because_that_pause_ends_the_invocation_with_its_own_code(
        self,
    ) -> None:
        row = self.row_of(ExitCode.WAIT_EXHAUSTED, _read(_ROOT / "README.md"))

        assert not self.mentions_the_alignment(row)

    @pytest.mark.parametrize("waited_for", ["integracion continua", "merge"])
    def test_the_row_names_what_the_run_was_waiting_for(self, waited_for: str) -> None:
        row = self.row_of(ExitCode.WAIT_EXHAUSTED, _read(_ROOT / "README.md"))

        assert waited_for in row

    @pytest.mark.parametrize(
        "row",
        [
            "| `7` | `run`: se agoto la espera de la alineacion |",
            "| `7` | `run`: se agoto la espera de la Alineacion |",
            "| `7` | `run`: se agoto la espera de la alineación |",
        ],
    )
    def test_the_check_catches_a_row_that_mentions_it(self, row: str) -> None:
        assert self.mentions_the_alignment(row)

    def test_a_table_without_the_row_fails_instead_of_passing_vacuously(self) -> None:
        with pytest.raises(AssertionError):
            self.row_of(ExitCode.WAIT_EXHAUSTED, "| `5` | otra cosa |")
