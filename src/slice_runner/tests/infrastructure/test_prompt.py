from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.prompt import JUDGE_PROMPT_PATH, read_agent_prompt

if TYPE_CHECKING:
    from pathlib import Path


def test_the_configuration_header_does_not_travel_as_an_instruction(tmp_path: Path) -> None:
    file = tmp_path / "judge.md"
    file.write_text(
        "---\nname: slice-verifier\ntools: Read, Grep, Glob\n---\n\n# Verificador\n\nBusca motivos para bloquear.\n",
        encoding="utf-8",
    )

    prompt = read_agent_prompt(file)

    assert prompt.startswith("# Verificador")
    assert "tools:" not in prompt


def test_a_prompt_with_no_header_is_read_as_is_including_a_later_separator(tmp_path: Path) -> None:
    file = tmp_path / "judge.md"
    file.write_text("# Verificador\n\n---\n\nSegunda seccion.\n", encoding="utf-8")

    assert read_agent_prompt(file) == "# Verificador\n\n---\n\nSegunda seccion."


def test_the_judge_prompt_of_this_repo_arrives_with_its_rubric_and_without_its_header() -> None:
    prompt = read_agent_prompt(JUDGE_PROMPT_PATH)

    assert "Rubrica cerrada" in prompt
    assert not prompt.startswith("---")
