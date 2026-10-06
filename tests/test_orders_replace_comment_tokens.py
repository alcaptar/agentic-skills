from __future__ import annotations

import pytest
from conftest import _ROOT, _read

from slice_runner.domain.order import Order
from slice_runner.infrastructure.cli import Cli
from slice_runner.infrastructure.subcommand import Subcommand


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
