from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.app import App
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static, Tree

from slice_panel.domain.follow_ended import FollowEnded
from slice_panel.domain.slice_board import SliceBoard
from slice_panel.infrastructure.herdr_tab_created_payload import HerdrTabCreatedRejectedError
from slice_panel.infrastructure.herdr_tabs import HerdrTabs
from slice_panel.infrastructure.slice_runner_commands import SliceRunnerCommands
from slice_panel.infrastructure.status_line_payload import StatusLinePayload, StatusRejectedError
from slice_panel.infrastructure.text_prompt import TextPrompt
from slice_panel.infrastructure.understanding_line_payload import UnderstandingLinePayload, UnderstandingRejectedError
from slice_panel.infrastructure.understanding_screen import UnderstandingScreen

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Sequence
    from pathlib import Path

    from textual.app import ComposeResult
    from textual.widgets.tree import TreeNode

    from slice_panel.domain.feature_group import FeatureGroup
    from slice_panel.domain.follow_line import FollowLine
    from slice_panel.domain.follow_source import FollowSource
    from slice_panel.domain.slice_view import SliceView
    from slice_panel.domain.tab_handle import TabHandle
    from slice_panel.infrastructure.process_launcher import ProcessLauncher
    from slice_panel.infrastructure.process_outcome import ProcessOutcome


class PanelApp(App[None]):
    CSS: ClassVar[str] = """
    #features { width: 40%; }
    #notice { dock: bottom; color: white; background: darkred; }
    #notice:empty { display: none; }
    """

    BINDINGS: ClassVar = [
        ("g", "go", "go"),
        ("r", "review", "review"),
        ("t", "retry", "retry"),
        ("l", "launch", "launch"),
        ("a", "add_feature", "add a feature"),
        ("e", "open_understanding", "understanding"),
    ]
    PREVIEW_LINES: ClassVar[int] = 8
    WORKERS: ClassVar[str] = "orders"

    def __init__(self, *, source: FollowSource, launcher: ProcessLauncher, clone_root: Path, repo: str) -> None:
        super().__init__()
        self._source = source
        self._launcher = launcher
        self._tabs = HerdrTabs(launcher=launcher)
        self._clone_root = clone_root
        self._repo = repo
        self._board = SliceBoard()
        self._selected: tuple[str, int] | None = None
        self._opened: dict[tuple[str, int], TabHandle] = {}
        self._understandings: dict[tuple[str, int], str] = {}
        self._asked: set[tuple[str, int]] = set()

    def compose(self) -> ComposeResult:
        with Horizontal():
            tree: Tree[tuple[str, int]] = Tree("features", id="features")
            tree.show_root = False
            yield tree
            with VerticalScroll():
                yield Static("", id="detail")
        yield Static("", id="notice")

    def on_mount(self) -> None:
        self.run_worker(self._consume(), exclusive=True)

    async def _consume(self) -> None:
        async for item in self._source.events():
            if isinstance(item, FollowEnded):
                self._announce(item)
            else:
                self._take(item)

    def _take(self, line: FollowLine) -> None:
        self._board = self._board.with_line(line)
        self._rebuild_tree()
        self._show_detail()

    def _announce(self, ended: FollowEnded) -> None:
        code = "" if ended.exit_code is None else f" (exit {ended.exit_code})"
        detail = f": {ended.detail}" if ended.detail else ""
        self.query_one("#notice", Static).update(f"follow ended{code}{detail}")

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[tuple[str, int]]) -> None:
        if event.node.data is not None:
            self._selected = event.node.data
            self._show_detail()

    def on_tree_node_selected(self, event: Tree.NodeSelected[tuple[str, int]]) -> None:
        if event.node.data is None:
            return
        self._say("")
        handle = self._opened.get(event.node.data)
        if handle is None:
            view = self._board.slice_of(repo=event.node.data[0], issue=event.node.data[1])
            name = "that slice" if view is None else view.slice_id
            self._say(f"the panel did not launch a run of {name}")
            return
        self._work(self._focus(handle))

    def action_go(self) -> None:
        view = self._chosen()
        if view is not None:
            self._work(self._give(view, SliceRunnerCommands.go(repo=view.repo, issue=view.issue)))

    def action_review(self) -> None:
        self._ask_for("correction for the understanding", self._reviewed)

    def action_retry(self) -> None:
        self._ask_for("instruction for the implementer", self._retried)

    def action_launch(self) -> None:
        view = self._chosen()
        if view is not None:
            self._work(self._launch(view))

    def action_add_feature(self) -> None:
        self._say("")
        self.push_screen(TextPrompt("number of the parent issue"), self._added)

    def action_open_understanding(self) -> None:
        view = self._chosen()
        if view is None:
            return
        text = self._understandings.get((view.repo, view.issue))
        if text is None:
            self._say(f"no understanding has been read for {view.slice_id}")
            return
        self.push_screen(UnderstandingScreen(text))

    def _chosen(self) -> SliceView | None:
        self._say("")
        view = None if self._selected is None else self._board.slice_of(repo=self._selected[0], issue=self._selected[1])
        if view is None:
            self._say("no slice is selected")

        return view

    def _ask_for(self, question: str, then: Callable[[SliceView, str], Coroutine[object, object, None]]) -> None:
        view = self._chosen()
        if view is None:
            return

        def answered(text: str | None) -> None:
            if text is not None:
                self._work(then(view, text))

        self.push_screen(TextPrompt(question), answered)

    def _reviewed(self, view: SliceView, text: str) -> Coroutine[object, object, None]:
        return self._give(view, SliceRunnerCommands.review(repo=view.repo, issue=view.issue, text=text))

    def _retried(self, view: SliceView, text: str) -> Coroutine[object, object, None]:
        return self._give(view, SliceRunnerCommands.retry(repo=view.repo, issue=view.issue, text=text))

    def _added(self, text: str | None) -> None:
        if text is None:
            return
        if not text.isdigit():
            self._say(f"`{text}` is not an issue number")
            return
        self._work(self._add(int(text)))

    def _work(self, work: Coroutine[object, object, None]) -> None:
        self.run_worker(work, group=self.WORKERS)

    def _say(self, text: str) -> None:
        self.query_one("#notice", Static).update(Text(text))

    async def _ran(self, argv: Sequence[str]) -> ProcessOutcome | None:
        try:
            outcome = await self._launcher.ran(argv, cwd=self._clone_root)
        except OSError as error:
            self._say(str(error))
            return None
        if outcome.exit_code != 0:
            self._say(outcome.stderr or outcome.stdout or f"`{' '.join(argv)}` exited {outcome.exit_code}")
            return None

        return outcome

    async def _give(self, view: SliceView, order: Sequence[str]) -> None:
        if await self._ran(order) is not None:
            await self._launch(view)

    async def _launch(self, view: SliceView) -> None:
        if view.parent is None:
            self._say(f"the feature of {view.slice_id} is unknown, so its run cannot be launched")
            return
        command = SliceRunnerCommands.run(repo=view.repo, parent=view.parent, slice_id=view.slice_id)
        try:
            self._opened[(view.repo, view.issue)] = await self._tabs.opened(
                command, cwd=self._clone_root, label=view.slice_id
            )
        except (OSError, HerdrTabCreatedRejectedError) as error:
            self._say(str(error))

    async def _focus(self, handle: TabHandle) -> None:
        try:
            await self._tabs.focused(handle)
        except OSError as error:
            self._say(str(error))

    async def _add(self, parent: int) -> None:
        outcome = await self._ran(SliceRunnerCommands.status(repo=self._repo, parent=parent))
        if outcome is None:
            return
        try:
            listings = StatusLinePayload.listings_of(outcome.stdout, repo=self._repo, parent=parent)
        except StatusRejectedError as error:
            self._say(str(error))
            return
        for listing in listings:
            self._board = self._board.with_listing(listing)
        self._rebuild_tree()
        self._show_detail()

    def _read_understanding_of_the_selected(self) -> None:
        view = None if self._selected is None else self._board.slice_of(repo=self._selected[0], issue=self._selected[1])
        if view is None or not view.waits_for_alignment() or (view.repo, view.issue) in self._asked:
            return
        self._asked.add((view.repo, view.issue))
        self._work(self._read_understanding(view))

    async def _read_understanding(self, view: SliceView) -> None:
        outcome = await self._ran(SliceRunnerCommands.understanding(repo=view.repo, issue=view.issue))
        if outcome is None:
            return
        try:
            self._understandings[(view.repo, view.issue)] = UnderstandingLinePayload.parsed(outcome.stdout).text
        except UnderstandingRejectedError as error:
            self._say(str(error))
            return
        self._show_detail()

    def _rebuild_tree(self) -> None:
        tree: Tree[tuple[str, int]] = self.query_one("#features", Tree)
        tree.clear()
        leaves: list[TreeNode[tuple[str, int]]] = []
        for group in self._board.groups():
            node = tree.root.add(self._group_label(group), expand=True)
            leaves.extend(node.add_leaf(self._slice_label(each), data=(each.repo, each.issue)) for each in group.slices)
        chosen = next((leaf for leaf in leaves if leaf.data == self._selected), leaves[0] if leaves else None)
        if chosen is not None:
            self._selected = chosen.data
            self.call_after_refresh(tree.move_cursor, chosen)

    @staticmethod
    def _group_label(group: FeatureGroup) -> str:
        return "no feature" if group.parent is None else f"feature {group.parent}"

    @staticmethod
    def _slice_label(view: SliceView) -> Text:
        title = f"{view.slice_id} {view.name}" if view.name else view.slice_id
        if view.waits_for_alignment():
            return Text(f"{title}  {view.status()}  <- waits for you", style="bold yellow")

        return Text(f"{title}  {view.status()}")

    def _show_detail(self) -> None:
        view = None if self._selected is None else self._board.slice_of(repo=self._selected[0], issue=self._selected[1])
        self.query_one("#detail", Static).update("" if view is None else self._detail_of(view))
        self._read_understanding_of_the_selected()

    def _detail_of(self, view: SliceView) -> str:
        events = "\n".join(f"{each.ts:%H:%M:%S} {each.step} {each.status}" for each in reversed(view.recent))
        header = f"{view.slice_id} {view.name}" if view.name else view.slice_id
        detail = (
            f"{header}\n"
            f"status: {view.status()}\n"
            f"step: {'never ran' if view.latest is None else view.latest.step}\n"
            f"spend: {self._spend_of(view)}\n"
            f"events:\n{events}"
        )
        understanding = self._understandings.get((view.repo, view.issue))
        if understanding is None or not view.waits_for_alignment():
            return detail
        preview = "\n".join(understanding.splitlines()[: self.PREVIEW_LINES])

        return f"{detail}\n\nunderstanding (e opens it whole):\n{preview}"

    @staticmethod
    def _spend_of(view: SliceView) -> str:
        if view.latest is not None:
            return f"${view.latest.cost_usd:.2f}"
        if view.listing is not None and view.listing.cost_usd is not None:
            return f"${view.listing.cost_usd:.2f}"

        return "n/a"
