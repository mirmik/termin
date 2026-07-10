"""Profiler panel for tcgui editor.

Toggleable right-side panel showing frame-time graph and
hierarchical section timings.  Activated via Debug → Profiler (F7).
"""

from __future__ import annotations

from tcbase import log
from tcgui.widgets.widget import Widget
from tcgui.widgets.basic import Label, Button, Checkbox
from tcgui.widgets.containers import VStack, HStack
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.tree import TreeWidget, TreeNode
from tcgui.widgets.frame_time_graph import FrameTimeGraph
from tcgui.widgets.units import px

from termin.editor_core.profiler_model import ProfilerController, ProfilerSnapshot


# Colors
_RED = (1.0, 0.39, 0.39, 1.0)
_YELLOW = (1.0, 0.78, 0.39, 1.0)
_TEXT = (0.75, 0.75, 0.75, 1.0)
_TEXT_DIM = (0.50, 0.50, 0.50, 1.0)


def _make_row_widget(name: str, cpu_ms: float, pct: float,
                     coverage: float, call_count: int,
                     has_children: bool) -> Widget:
    """Build an HStack with fixed-width columns for a tree node."""
    row = HStack()
    row.spacing = 4

    name_lbl = Label()
    name_lbl.text = name
    name_lbl.text_color = _TEXT
    name_lbl.font_size = 12
    name_lbl.stretch = True
    row.add_child(name_lbl)

    time_lbl = Label()
    time_lbl.text = f"{cpu_ms:.2f}"
    time_lbl.font_size = 12
    time_lbl.preferred_width = px(60)
    if pct > 50:
        time_lbl.text_color = _RED
    elif pct > 25:
        time_lbl.text_color = _YELLOW
    else:
        time_lbl.text_color = _TEXT
    row.add_child(time_lbl)

    pct_lbl = Label()
    pct_lbl.text = f"{pct:.1f}%"
    pct_lbl.font_size = 12
    pct_lbl.preferred_width = px(50)
    pct_lbl.text_color = _TEXT
    row.add_child(pct_lbl)

    cov_lbl = Label()
    if has_children:
        cov_lbl.text = f"{coverage:.0f}%"
        if coverage < 50:
            cov_lbl.text_color = _RED
        elif coverage < 80:
            cov_lbl.text_color = _YELLOW
        else:
            cov_lbl.text_color = _TEXT_DIM
    else:
        cov_lbl.text = ""
        cov_lbl.text_color = _TEXT_DIM
    cov_lbl.font_size = 12
    cov_lbl.preferred_width = px(45)
    row.add_child(cov_lbl)

    cnt_lbl = Label()
    cnt_lbl.text = str(call_count) if call_count > 1 else ""
    cnt_lbl.font_size = 12
    cnt_lbl.preferred_width = px(40)
    cnt_lbl.text_color = _TEXT_DIM
    row.add_child(cnt_lbl)

    return row


class ProfilerPanel(VStack):
    """Profiler debug panel (right-side, toggled by F7)."""

    def __init__(self):
        super().__init__()
        self.spacing = 4

        from termin.engine import EngineCore

        engine = EngineCore.instance()

        def get_include_ui() -> bool:
            return bool(engine.profile_ui) if engine is not None else False

        def set_include_ui(enabled: bool) -> None:
            if engine is None:
                log.error("[ProfilerPanel] cannot set profile_ui without EngineCore")
                raise RuntimeError("cannot set profile_ui without EngineCore")
            engine.profile_ui = enabled

        self._controller = ProfilerController(
            get_include_ui=get_include_ui,
            set_include_ui=set_include_ui,
        )

        self._build_ui()

    def _build_ui(self) -> None:
        # Toolbar
        toolbar = HStack()
        toolbar.spacing = 8
        toolbar.preferred_height = px(28)

        self._enable_check = Checkbox()
        self._enable_check.text = "Enable"
        self._enable_check.font_size = 12
        self._enable_check.checked = self._controller.enabled
        self._enable_check.on_changed = self._on_enable_toggled
        toolbar.add_child(self._enable_check)

        self._detailed_check = Checkbox()
        self._detailed_check.text = "Detailed"
        self._detailed_check.font_size = 12
        self._detailed_check.checked = self._controller.detailed
        self._detailed_check.on_changed = self._on_detailed_toggled
        toolbar.add_child(self._detailed_check)

        self._include_ui_check = Checkbox()
        self._include_ui_check.text = "Include UI"
        self._include_ui_check.font_size = 12
        self._include_ui_check.on_changed = self._on_include_ui_toggled
        self._include_ui_check.checked = self._controller.include_ui
        toolbar.add_child(self._include_ui_check)

        clear_btn = Button()
        clear_btn.text = "Clear"
        clear_btn.font_size = 11
        clear_btn.padding = 4
        clear_btn.preferred_width = px(50)
        clear_btn.on_click = self._on_clear
        toolbar.add_child(clear_btn)

        spacer = Label()
        spacer.stretch = True
        toolbar.add_child(spacer)

        self._fps_label = Label()
        self._fps_label.text = "-- FPS"
        self._fps_label.font_size = 14
        self._fps_label.text_color = (1.0, 1.0, 1.0, 1.0)
        toolbar.add_child(self._fps_label)

        self.add_child(toolbar)

        # Graph
        self._graph = FrameTimeGraph()
        self._graph.preferred_height = px(80)
        self.add_child(self._graph)

        # Header row
        header = HStack()
        header.spacing = 4
        header.preferred_height = px(20)

        def _hdr(text, width=None, stretch=False):
            lbl = Label()
            lbl.text = text
            lbl.font_size = 11
            lbl.text_color = _TEXT_DIM
            if width:
                lbl.preferred_width = px(width)
            if stretch:
                lbl.stretch = True
            return lbl

        header.add_child(_hdr("Section", stretch=True))
        header.add_child(_hdr("ms", 60))
        header.add_child(_hdr("%", 50))
        header.add_child(_hdr("Cov", 45))
        header.add_child(_hdr("N", 40))
        self.add_child(header)

        # Tree
        scroll = ScrollArea()
        scroll.stretch = True
        self._tree = TreeWidget()
        self._tree.row_height = 22
        self._tree.font_size = 12
        scroll.add_child(self._tree)
        self.add_child(scroll)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_enable_toggled(self, checked: bool) -> None:
        self._controller.set_enabled(checked)
        if not checked:
            self._reset_state()

    def _on_detailed_toggled(self, checked: bool) -> None:
        self._controller.set_detailed(checked)

    def _on_include_ui_toggled(self, checked: bool) -> None:
        self._controller.set_include_ui(checked)

    def _on_clear(self) -> None:
        self._controller.clear()
        self._reset_state()

    def _reset_state(self) -> None:
        self._graph.clear()
        self._tree.clear()
        self._fps_label.text = "-- FPS"

    # ------------------------------------------------------------------
    # Update (called from editor_window.poll at ~10 Hz)
    # ------------------------------------------------------------------

    def update_display(self) -> None:
        snapshot = self._controller.poll()
        if snapshot is None:
            return
        self._fps_label.text = f"{snapshot.fps:.0f} FPS ({snapshot.frame_ms:.1f}ms)"
        self._graph.add_frame(snapshot.frame_ms)
        self._rebuild_tree(snapshot)

    # ------------------------------------------------------------------
    # Tree rebuild
    # ------------------------------------------------------------------

    def _rebuild_tree(self, snapshot: ProfilerSnapshot) -> None:
        # Save expanded paths
        expanded = self._get_expanded_paths()

        self._tree.clear()

        node_map: dict[str, TreeNode] = {}

        for section in snapshot.rows:
            path = section.path
            parts = path.split("/")

            row = _make_row_widget(
                section.name,
                section.cpu_ms,
                section.percent,
                section.coverage_percent,
                section.call_count,
                section.has_children,
            )
            node = TreeNode(content=row)
            node.data = path

            if len(parts) == 1:
                self._tree.add_root(node)
                node_map[path] = node
            else:
                parent_path = "/".join(parts[:-1])
                parent = node_map.get(parent_path)
                if parent:
                    parent.add_node(node)
                    node_map[path] = node
                else:
                    self._tree.add_root(node)
                    node_map[path] = node

        # Restore expanded state (default: expand roots)
        for path, node in node_map.items():
            if expanded:
                node.expanded = path in expanded
            else:
                node.expanded = "/" not in path

    def _get_expanded_paths(self) -> set:
        result = set()

        def _collect(node: TreeNode):
            if node.expanded and node.data:
                result.add(node.data)
            for child in node.subnodes:
                _collect(child)

        for root in self._tree.root_nodes:
            _collect(root)
        return result
