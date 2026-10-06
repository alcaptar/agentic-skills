from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pytest
from textual.widgets import Static, Tree

from slice_panel.domain.follow_ended import FollowEnded
from slice_panel.domain.follow_line import FollowLine
from slice_panel.infrastructure.cli import Cli
from slice_panel.infrastructure.panel_app import PanelApp
from slice_panel.infrastructure.subprocess_follow_source import SubprocessFollowSource

if TYPE_CHECKING:
    from slice_panel.domain.follow_source import FollowSource


class RealProcess:
    EXAMPLES: ClassVar[Path] = Path(__file__).resolve().parents[4] / "contract" / "follow-line.json"

    @classmethod
    def example_lines(cls, **extra: object) -> list[str]:
        examples = json.loads(cls.EXAMPLES.read_text(encoding="utf-8"))["examples"]

        return [json.dumps({**example, **extra}) for example in examples]

    @staticmethod
    def printing(*, stdout: str = "", stderr: str = "", exit_code: int = 0) -> tuple[str, ...]:
        script = f"import sys\nsys.stdout.write({stdout!r})\nsys.stderr.write({stderr!r})\nsys.exit({exit_code})\n"

        return (sys.executable, "-c", script)

    @staticmethod
    async def collected(source: FollowSource) -> list[FollowLine | FollowEnded]:
        return [item async for item in source.events()]


@pytest.mark.integration
class TestTheProcessThatFollowIs(RealProcess):
    async def test_each_stdout_line_arrives_as_a_follow_line_and_the_end_is_announced(self) -> None:
        stdout = "".join(f"{line}\n" for line in self.example_lines())

        items = await self.collected(SubprocessFollowSource(argv=self.printing(stdout=stdout)))

        first = items[0]
        assert isinstance(first, FollowLine)
        assert (first.slice_id, first.status) == ("slice-05", "closed")
        assert [type(item) for item in items] == [FollowLine, FollowLine, FollowEnded]
        assert items[-1] == FollowEnded(exit_code=0, detail="")

    async def test_a_failing_process_ends_with_its_exit_code_and_its_stderr(self) -> None:
        items = await self.collected(SubprocessFollowSource(argv=self.printing(stderr="boom\n", exit_code=3)))

        assert items == [FollowEnded(exit_code=3, detail="boom")]

    async def test_an_executable_that_cannot_be_started_ends_without_an_exit_code(self) -> None:
        items = await self.collected(SubprocessFollowSource(argv=("this-executable-does-not-exist",)))

        assert len(items) == 1
        ended = items[0]
        assert isinstance(ended, FollowEnded)
        assert ended.exit_code is None
        assert "this-executable-does-not-exist" in ended.detail

    async def test_a_corrupt_line_ends_the_stream_saying_which_line_it_was(self) -> None:
        items = await self.collected(SubprocessFollowSource(argv=self.printing(stdout="not json\n")))

        assert len(items) == 1
        ended = items[0]
        assert isinstance(ended, FollowEnded)
        assert ended.exit_code is None
        assert "not JSON" in ended.detail


@pytest.mark.integration
class TestTheRealPanelOverTheLinesOfTheContract(RealProcess):
    async def test_the_screen_shows_the_examples_of_follow_even_when_the_lines_carry_unknown_keys(self) -> None:
        stdout = "".join(f"{line}\n" for line in self.example_lines(key_from_the_future="x"))
        source = SubprocessFollowSource(argv=self.printing(stdout=stdout))

        async with PanelApp(source=source).run_test() as pilot:
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            tree = pilot.app.query_one("#features", Tree)
            groups = [str(node.label) for node in tree.root.children]
            detail = str(pilot.app.query_one("#detail", Static).content)

        assert groups == ["feature 140"]
        assert "slice-05" in detail
        assert "key_from_the_future" not in detail

    async def test_the_screen_says_follow_ended_when_the_process_fails(self) -> None:
        source = SubprocessFollowSource(argv=self.printing(stderr="no network\n", exit_code=4))

        async with PanelApp(source=source).run_test() as pilot:
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            notice = str(pilot.app.query_one("#notice", Static).content)

        assert "follow ended" in notice
        assert "exit 4" in notice
        assert "no network" in notice


@pytest.mark.integration
class TestTheCommandTheCliLaunches(RealProcess):
    async def test_it_is_slice_runner_follow_json_found_on_the_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        executable = tmp_path / "slice-runner"
        executable.write_text('#!/bin/sh\necho "$@" >&2\nexit 7\n', encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
        monkeypatch.setenv("PATH", str(tmp_path))

        items = await self.collected(Cli.follow_source())

        assert items == [FollowEnded(exit_code=7, detail="follow --json")]
