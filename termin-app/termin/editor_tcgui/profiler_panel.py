"""Profiler panel for tcgui editor.

Toggleable right-side panel showing frame-time graph and
hierarchical section timings.  Activated via Debug → Profiler (F7).
"""

from __future__ import annotations

from typing import Dict

from tcbase import log
from tcgui.widgets.widget import Widget
from tcgui.widgets.basic import Label, Button, Checkbox
from tcgui.widgets.containers import VStack, HStack
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.tree import TreeWidget, TreeNode
from tcgui.widgets.frame_time_graph import FrameTimeGraph
from tcgui.widgets.units import px

from termin.core.profiler import Profiler, SectionStats


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

        self._profiler = Profiler.instance()

        # EMA state
        self._ema_sections: Dict[str, float] = {}
        self._ema_children: Dict[str, float] = {}
        self._ema_calls: Dict[str, int] = {}
        self._ema_total: float | None = None
        self._ema_alpha: float = 0.1
        self._last_sections: Dict[str, SectionStats] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        # Toolbar
        toolbar = HStack()
        toolbar.spacing = 8
        toolbar.preferred_height = px(28)

        self._enable_check = Checkbox()
        self._enable_check.text = "Enable"
        self._enable_check.font_size = 12
        self._enable_check.on_changed = self._on_enable_toggled
        toolbar.add_child(self._enable_check)

        self._detailed_check = Checkbox()
        self._detailed_check.text = "Detailed"
        self._detailed_check.font_size = 12
        self._detailed_check.on_changed = self._on_detailed_toggled
        toolbar.add_child(self._detailed_check)

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
        self._profiler.enabled = checked
        if not checked:
            self._reset_state()

    def _on_detailed_toggled(self, checked: bool) -> None:
        self._profiler.detailed_rendering = checked

    def _on_clear(self) -> None:
        self._profiler.clear_history()
        self._reset_state()

    def _reset_state(self) -> None:
        self._graph.clear()
        self._tree.clear()
        self._fps_label.text = "-- FPS"
        self._last_sections.clear()
        self._ema_sections.clear()
        self._ema_children.clear()
        self._ema_calls.clear()
        self._ema_total = None

    # ------------------------------------------------------------------
    # Update (called from editor_window.poll at ~10 Hz)
    # ------------------------------------------------------------------

    def update_display(self) -> None:
        if not self._profiler.enabled:
            return

        tc = self._profiler._tc
        count = tc.history_count
        if count <= 0:
            return

        frame = tc.history_at(count - 1)
        detailed = self._collect_sections(frame)
        if not detailed:
            return

        total = sum(s.cpu_ms for k, s in detailed.items() if "/" not in k)
        total_ema = self._update_total_ema(total)
        detailed_ema = self._update_sections_ema(detailed)

        # FPS label
        if total_ema > 0:
            fps = 1000.0 / total_ema
            self._fps_label.text = f"{fps:.0f} FPS ({total_ema:.1f}ms)"
        else:
            self._fps_label.text = "-- FPS"

        # Graph
        self._graph.add_frame(total_ema)

        # Rebuild tree if data changed significantly
        if self._should_update(detailed_ema):
            self._rebuild_tree(detailed_ema, total_ema)
            self._last_sections = detailed_ema.copy()

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------

    def _collect_sections(self, frame) -> Dict[str, SectionStats]:
        sections = frame.sections
        if not sections:
            return {}

        names = [s.name for s in sections]
        parents = [s.parent_index for s in sections]
        path_cache: Dict[int, str] = {}

        def make_path(idx: int) -> str:
            cached = path_cache.get(idx)
            if cached is not None:
                return cached
            parent_idx = parents[idx]
            if parent_idx < 0:
                path = names[idx]
            else:
                path = f"{make_path(parent_idx)}/{names[idx]}"
            path_cache[idx] = path
            return path

        result: Dict[str, SectionStats] = {}
        for i, s in enumerate(sections):
            path = make_path(i)
            result[path] = SectionStats(
                cpu_ms=s.cpu_ms,
                children_ms=s.children_ms,
                call_count=s.call_count,
            )
        return result

    # ------------------------------------------------------------------
    # EMA
    # ------------------------------------------------------------------

    def _update_total_ema(self, total: float) -> float:
        if self._ema_total is None:
            self._ema_total = total
        else:
            self._ema_total = self._ema_total * (1.0 - self._ema_alpha) + total * self._ema_alpha
        return self._ema_total

    def _update_sections_ema(self, detailed: Dict[str, SectionStats]) -> Dict[str, SectionStats]:
        alpha = self._ema_alpha
        for key, stats in detailed.items():
            prev = self._ema_sections.get(key)
            prev_ch = self._ema_children.get(key)
            if prev is None:
                self._ema_sections[key] = stats.cpu_ms
                self._ema_children[key] = stats.children_ms
            else:
                self._ema_sections[key] = prev * (1.0 - alpha) + stats.cpu_ms * alpha
                self._ema_children[key] = (prev_ch or 0.0) * (1.0 - alpha) + stats.children_ms * alpha
            self._ema_calls[key] = stats.call_count

        for key in list(self._ema_sections.keys()):
            if key in detailed:
                continue
            self._ema_sections[key] *= (1.0 - alpha)
            self._ema_children[key] = self._ema_children.get(key, 0.0) * (1.0 - alpha)
            if self._ema_sections[key] < 0.01:
                self._ema_sections.pop(key, None)
                self._ema_children.pop(key, None)
                self._ema_calls.pop(key, None)

        return {
            key: SectionStats(
                cpu_ms=self._ema_sections[key],
                children_ms=self._ema_children.get(key, 0.0),
                call_count=self._ema_calls.get(key, 0),
            )
            for key in self._ema_sections
        }

    def _should_update(self, detailed: Dict[str, SectionStats]) -> bool:
        if len(detailed) != len(self._last_sections):
            return True
        for key, stats in detailed.items():
            old = self._last_sections.get(key)
            if old is None:
                if stats.cpu_ms > 0.1:
                    return True
            elif old.cpu_ms > 0 and abs(stats.cpu_ms - old.cpu_ms) / old.cpu_ms > 0.05:
                return True
        return False

    # ------------------------------------------------------------------
    # Tree rebuild
    # ------------------------------------------------------------------

    def _rebuild_tree(self, detailed: Dict[str, SectionStats], total: float) -> None:
        # Save expanded paths
        expanded = self._get_expanded_paths()

        self._tree.clear()

        sorted_sections = sorted(
            detailed.items(),
            key=lambda x: (x[0].count("/"), -x[1].cpu_ms),
        )

        node_map: Dict[str, TreeNode] = {}

        for path, stats in sorted_sections:
            parts = path.split("/")
            pct = (stats.cpu_ms / total * 100) if total > 0 else 0
            coverage = (stats.children_ms / stats.cpu_ms * 100) if stats.cpu_ms > 0 else 0
            has_children = stats.children_ms > 0

            row = _make_row_widget(
                parts[-1], stats.cpu_ms, pct, coverage,
                stats.call_count, has_children,
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
