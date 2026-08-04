from __future__ import annotations

from typing import TYPE_CHECKING

from slice_runner.infrastructure.agent_prompt import AgentPrompt

if TYPE_CHECKING:
    from pathlib import Path


class TestAgentPrompt:
    def test_the_configuration_header_does_not_travel_as_an_instruction(self, tmp_path: Path) -> None:
        file = tmp_path / "judge.md"
        file.write_text(
            "---\nname: slice-verifier\ntools: Read, Grep, Glob\n---\n"
            "\n# Verificador\n\nBusca motivos para bloquear.\n",
            encoding="utf-8",
        )

        prompt = AgentPrompt.read(file)

        assert prompt.startswith("# Verificador")
        assert "tools:" not in prompt

    def test_a_prompt_with_no_header_is_read_as_is_including_a_later_separator(self, tmp_path: Path) -> None:
        file = tmp_path / "judge.md"
        file.write_text("# Verificador\n\n---\n\nSegunda seccion.\n", encoding="utf-8")

        assert AgentPrompt.read(file) == "# Verificador\n\n---\n\nSegunda seccion."

    def test_the_judge_prompt_of_this_repo_arrives_with_its_rubric_and_without_its_header(self) -> None:
        prompt = AgentPrompt.read(AgentPrompt.JUDGE)

        assert "Rubrica cerrada" in prompt
        assert not prompt.startswith("---")
