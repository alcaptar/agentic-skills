from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.app import App
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static, Tree

from slice_panel.domain.follow_ended import FollowEnded
from slice_panel.domain.slice_board import SliceBoard

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.widgets.tree import TreeNode

    from slice_panel.domain.feature_group import FeatureGroup
    from slice_panel.domain.follow_line import FollowLine
    from slice_panel.domain.follow_source import FollowSource
    from slice_panel.domain.slice_view import SliceView


class PanelApp(App[None]):
    CSS: ClassVar[str] = """
    #features { width: 40%; }
    #notice { dock: bottom; color: white; background: darkred; }
    #notice:empty { display: none; }
    """

    def __init__(self, *, source: FollowSource) -> None:
        super().__init__()
        self._source = source
        self._board = SliceBoard()
        self._selected: tuple[str, int] | None = None

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
        if view.awaits_a_person():
            return Text(f"{title}  {view.latest.status}  <- waits for you", style="bold yellow")

        return Text(f"{title}  {view.latest.status}")

    def _show_detail(self) -> None:
        view = None if self._selected is None else self._board.slice_of(repo=self._selected[0], issue=self._selected[1])
        self.query_one("#detail", Static).update("" if view is None else self._detail_of(view))

    @staticmethod
    def _detail_of(view: SliceView) -> str:
        events = "\n".join(f"{each.ts:%H:%M:%S} {each.step} {each.status}" for each in reversed(view.recent))
        header = f"{view.slice_id} {view.name}" if view.name else view.slice_id

        return (
            f"{header}\n"
            f"status: {view.latest.status}\n"
            f"step: {view.latest.step}\n"
            f"spend: ${view.latest.cost_usd:.2f}\n"
            f"events:\n{events}"
        )
