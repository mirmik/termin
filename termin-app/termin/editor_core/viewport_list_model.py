"""Toolkit-neutral display, viewport, entity and render-target tree model."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Iterable

from termin.editor_core.signal import Signal


_logger = logging.getLogger(__name__)


class ViewportNodeKind:
    DISPLAY = "display"
    VIEWPORT = "viewport"
    ENTITY = "entity"
    RENDER_TARGET_GROUP = "render_target_group"
    RENDER_TARGET = "render_target"


@dataclass(frozen=True)
class ViewportListNode:
    stable_id: str
    label: str
    kind: str
    value: Any = None
    children: tuple["ViewportListNode", ...] = ()


@dataclass(frozen=True)
class ViewportListSnapshot:
    roots: tuple[ViewportListNode, ...]
    selected_id: str | None = None

    def find(self, stable_id: str) -> ViewportListNode | None:
        def visit(nodes: tuple[ViewportListNode, ...]) -> ViewportListNode | None:
            for node in nodes:
                if node.stable_id == stable_id:
                    return node
                found = visit(node.children)
                if found is not None:
                    return found
            return None

        return visit(self.roots)


class ViewportListController:
    """Own the rendering tree snapshot and its toolkit-independent actions."""

    def __init__(self) -> None:
        self._displays: list[Any] = []
        self._display_names: dict[int, str] = {}
        self._render_targets: list[Any] = []
        self._selected_id: str | None = None
        self._nodes: dict[str, ViewportListNode] = {}
        self._viewport_displays: dict[str, Any] = {}
        self._snapshot = ViewportListSnapshot(())

        self.snapshot_changed = Signal()
        self.display_selected = Signal()
        self.viewport_selected = Signal()
        self.entity_selected = Signal()
        self.render_target_selected = Signal()
        self.display_add_requested = Signal()
        self.viewport_add_requested = Signal()
        self.display_remove_requested = Signal()
        self.viewport_remove_requested = Signal()
        self.viewport_renamed = Signal()
        self.render_target_add_requested = Signal()
        self.render_target_remove_requested = Signal()
        self.render_target_renamed = Signal()

    @property
    def snapshot(self) -> ViewportListSnapshot:
        return self._snapshot

    @property
    def displays(self) -> tuple[Any, ...]:
        return tuple(self._displays)

    @property
    def render_targets(self) -> tuple[Any, ...]:
        return tuple(self._render_targets)

    def set_displays(self, displays: Iterable[Any]) -> ViewportListSnapshot:
        self._displays = list(displays)
        return self.refresh()

    def set_display_name(self, display: Any, name: str) -> ViewportListSnapshot:
        self._display_names[self.display_stable_key(display)] = name
        return self.refresh()

    def get_display_name(self, display: Any) -> str:
        explicit = self._display_names.get(self.display_stable_key(display))
        if explicit is not None:
            return explicit
        try:
            index = self._displays.index(display)
        except ValueError:
            index = 0
        return f"Display {index}"

    def add_display(self, display: Any, name: str | None = None) -> ViewportListSnapshot:
        if display not in self._displays:
            self._displays.append(display)
        if name is not None:
            self._display_names[self.display_stable_key(display)] = name
        return self.refresh()

    def remove_display(self, display: Any) -> ViewportListSnapshot:
        if display in self._displays:
            self._displays.remove(display)
        self._display_names.pop(self.display_stable_key(display), None)
        return self.refresh()

    def set_render_targets(self, render_targets: Iterable[Any] | None) -> ViewportListSnapshot:
        self._render_targets = list(render_targets or ())
        return self.refresh()

    def refresh(self) -> ViewportListSnapshot:
        roots = []
        self._nodes.clear()
        self._viewport_displays.clear()
        for display_index, display in enumerate(self._displays):
            if not self._display_valid(display):
                continue
            display_id = self.display_stable_id(display)
            viewport_nodes = []
            for viewport_index, viewport in enumerate(display.viewports):
                viewport_id = self.viewport_stable_id(viewport)
                viewport_name = viewport.name or f"Viewport {viewport_index}"
                render_target = viewport.render_target
                render_target_name = (
                    "No Render Target" if render_target is None else render_target.name or "RenderTarget"
                )
                children = ()
                internal = viewport.internal_entities
                if internal is not None:
                    entity_node = self._entity_node(internal)
                    children = () if entity_node is None else (entity_node,)
                node = ViewportListNode(
                    viewport_id,
                    f"{viewport_name} ({render_target_name})",
                    ViewportNodeKind.VIEWPORT,
                    viewport,
                    children,
                )
                viewport_nodes.append(node)
                self._viewport_displays[viewport_id] = display
            display_name = self._display_names.get(
                self.display_stable_key(display),
                display.name or f"Display {display_index}",
            )
            roots.append(
                ViewportListNode(
                    display_id,
                    display_name,
                    ViewportNodeKind.DISPLAY,
                    display,
                    tuple(viewport_nodes),
                )
            )

        if self._render_targets:
            roots.append(
                ViewportListNode(
                    "render-targets",
                    "Render Targets",
                    ViewportNodeKind.RENDER_TARGET_GROUP,
                    children=tuple(self._render_target_node(target) for target in self._render_targets),
                )
            )
        self._index_nodes(tuple(roots))
        if self._selected_id not in self._nodes:
            self._selected_id = None
        self._snapshot = ViewportListSnapshot(tuple(roots), self._selected_id)
        self.snapshot_changed.emit(self._snapshot)
        return self._snapshot

    def select(self, stable_id: str | None) -> ViewportListNode | None:
        node = None if stable_id is None else self._nodes.get(stable_id)
        self._selected_id = None if node is None else node.stable_id
        self._snapshot = ViewportListSnapshot(self._snapshot.roots, self._selected_id)
        if node is None:
            self.display_selected.emit(None)
            self.viewport_selected.emit(None)
            self.entity_selected.emit(None)
            self.render_target_selected.emit(None)
        elif node.kind == ViewportNodeKind.ENTITY:
            entity = node.value
            self.entity_selected.emit(entity if entity.valid() else None)
        elif node.kind == ViewportNodeKind.RENDER_TARGET:
            self.render_target_selected.emit(node.value)
        elif node.kind == ViewportNodeKind.VIEWPORT:
            self.viewport_selected.emit(node.value)
            self.entity_selected.emit(None)
        elif node.kind == ViewportNodeKind.DISPLAY:
            self.display_selected.emit(node.value)
            self.viewport_selected.emit(None)
            self.entity_selected.emit(None)
        self.snapshot_changed.emit(self._snapshot)
        return node

    def selected_display(self) -> Any | None:
        if self._selected_id is None:
            return None
        node = self._nodes.get(self._selected_id)
        if node is None:
            return None
        if node.kind == ViewportNodeKind.DISPLAY:
            return node.value
        if node.kind == ViewportNodeKind.VIEWPORT:
            return self._viewport_displays.get(node.stable_id)
        return None

    def request_add_display(self) -> None:
        self.display_add_requested.emit()

    def request_add_viewport(self, display: Any | None = None) -> None:
        target = display if display is not None else self.selected_display()
        if target is not None:
            self.viewport_add_requested.emit(target)

    def request_remove(self, stable_id: str) -> None:
        node = self._nodes.get(stable_id)
        if node is None:
            _logger.error("Cannot remove unknown viewport-list node '%s'", stable_id)
            raise KeyError(stable_id)
        if node.kind == ViewportNodeKind.DISPLAY:
            self.display_remove_requested.emit(node.value)
        elif node.kind == ViewportNodeKind.VIEWPORT:
            self.viewport_remove_requested.emit(node.value)
        elif node.kind == ViewportNodeKind.RENDER_TARGET:
            self.render_target_remove_requested.emit(node.value)
        else:
            _logger.error("Viewport-list node '%s' is not removable", stable_id)
            raise ValueError(f"node '{stable_id}' is not removable")

    def request_add_render_target(self, kind: str = "texture_2d") -> None:
        if kind not in ("texture_2d", "xr_stereo"):
            _logger.error("Unknown render target kind '%s'", kind)
            raise ValueError(f"unknown render target kind '{kind}'")
        self.render_target_add_requested.emit(kind)

    def rename(self, stable_id: str, name: str) -> ViewportListSnapshot:
        node = self._nodes.get(stable_id)
        if node is None:
            _logger.error("Cannot rename unknown viewport-list node '%s'", stable_id)
            raise KeyError(stable_id)
        normalized = name.strip()
        if not normalized:
            _logger.error("Cannot assign an empty viewport-list name")
            raise ValueError("name cannot be empty")
        if node.kind == ViewportNodeKind.VIEWPORT:
            node.value.name = normalized
            self.viewport_renamed.emit(node.value, normalized)
        elif node.kind == ViewportNodeKind.RENDER_TARGET:
            node.value.name = normalized
            self.render_target_renamed.emit(node.value, normalized)
        else:
            _logger.error("Viewport-list node '%s' is not renameable", stable_id)
            raise ValueError(f"node '{stable_id}' is not renameable")
        return self.refresh()

    def _entity_node(self, entity: Any) -> ViewportListNode | None:
        if not entity.valid():
            return None
        children = []
        for child_transform in entity.transform.children:
            child = child_transform.entity
            if child is None:
                continue
            child_node = self._entity_node(child)
            if child_node is not None:
                children.append(child_node)
        label = entity.name or f"Entity ({entity.uuid[:8]})"
        return ViewportListNode(
            f"entity:{entity.uuid}",
            label,
            ViewportNodeKind.ENTITY,
            entity,
            tuple(children),
        )

    @staticmethod
    def _render_target_node(render_target: Any) -> ViewportListNode:
        name = render_target.name or "RenderTarget"
        label = f"{name} [XR Stereo]" if render_target.kind == "xr_stereo" else name
        return ViewportListNode(
            ViewportListController.render_target_stable_id(render_target),
            label,
            ViewportNodeKind.RENDER_TARGET,
            render_target,
        )

    def _index_nodes(self, nodes: tuple[ViewportListNode, ...]) -> None:
        for node in nodes:
            self._nodes[node.stable_id] = node
            self._index_nodes(node.children)

    @staticmethod
    def _display_valid(display: Any) -> bool:
        try:
            _display_pointer = display.tc_display_ptr
            return True
        except (AttributeError, RuntimeError, ReferenceError):
            _logger.exception("Skipping invalid display in viewport list")
            return False

    @staticmethod
    def display_stable_key(display: Any) -> int:
        return int(display.tc_display_ptr)

    @staticmethod
    def display_stable_id(display: Any) -> str:
        return f"display:{ViewportListController.display_stable_key(display)}"

    @staticmethod
    def viewport_stable_id(viewport: Any) -> str:
        index, generation = viewport._viewport_handle()
        return f"viewport:{index}:{generation}"

    @staticmethod
    def render_target_stable_id(render_target: Any) -> str:
        return f"render-target:{render_target.index}:{render_target.generation}"


__all__ = [
    "ViewportListController",
    "ViewportListNode",
    "ViewportListSnapshot",
    "ViewportNodeKind",
]
