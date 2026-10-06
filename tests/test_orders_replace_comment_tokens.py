from __future__ import annotations

from typing import ClassVar

import pytest
from conftest import _ROOT, _read

from slice_runner.domain.order import Order
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.subcommand import Subcommand


class TestNoSurfaceTeachesTheCommentTokens:
    TOKENS: ClassVar[tuple[str, ...]] = ("-GO", "-REVIEW", "-RETRY")
    SURFACES: ClassVar[tuple[str, ...]] = (
        "src/slice_runner/infrastructure/understanding_comment.py",
        "README.md",
        "skills/slice-spec/SKILL.md",
        "docs/arranque.md",
        "skills/slice-spec/references/diseno.md",
    )

    @pytest.mark.parametrize("surface", SURFACES)
    def test_a_surface_a_person_reads_never_names_a_token_the_run_no_longer_reads(self, surface: str) -> None:
        text = _read(_ROOT / surface)

        assert [token for token in self.TOKENS if token in text] == []


class TestEveryOrderIsASubcommandTheReadmeDocuments:
    @pytest.mark.parametrize("order", list(Order))
    def test_the_order_is_a_subcommand_of_the_program(self, order: Order) -> None:
        assert str(order) in {str(subcommand) for subcommand in Subcommand}

    @pytest.mark.parametrize("order", list(Order))
    def test_the_command_table_of_the_readme_has_a_row_for_it(self, order: Order) -> None:
        assert f"| `{order}` |" in _read(_ROOT / "README.md")

    @pytest.mark.parametrize("order", list(Order))
    def test_the_parser_knows_it(self, order: Order) -> None:
        assert str(order) in Cli.parser().format_help()
