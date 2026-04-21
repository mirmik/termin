"""ViewportListWidgetTcgui — tree widget showing Displays, Viewports, Render Targets.

tcgui port of ``termin.editor.viewport_list_widget.ViewportListWidget``.
Same Signal-based public API so the RenderingController wires it up the
same way regardless of UI framework.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.input_dialog import show_input_dialog
from tcgui.widgets.label import Label
from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack

from termin.editor_core.signal import Signal

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.entity import Entity


class _NodeKind:
    DISPLAY = "display"
    VIEWPORT = "viewport"
    ENTITY = "entity"
    RENDER_TARGET_GROUP = "rt_group"
    RENDER_TARGET = "render_target"


class _NodePayload:
    kind: str
    obj: object | None

    def __init__(self, kind: str, obj: object | None = None):
        self.kind = kind
        self.obj = obj


class ViewportListWidgetTcgui(VStack):
    """Displays a Display → Viewport → Entity tree plus a Render Targets section.

    Public API mirrors the Qt ViewportListWidget so RenderingController can
    wire selection / add / remove signals identically. Signals are
    editor_core.Signal instances (connect/emit) rather than pyqtSignal.
    """

    def __init__(self):
        super().__init__()
        self.spacing = 4

        self._displays: list["Display"] = []
        self._display_names: dict[int, str] = {}
        self._render_targets: list = []

        self._ui = None
        self._ctx_menu = Menu()

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

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        toolbar = HStack()
        toolbar.spacing = 4
        toolbar.preferred_height = px(24)

        self._add_display_btn = Button()
        self._add_display_btn.text = "+ Display"
        self._add_display_btn.on_click = lambda: self.display_add_requested.emit()
        toolbar.add_child(self._add_display_btn)

        self._add_viewport_btn = Button()
        self._add_viewport_btn.text = "+ Viewport"
        self._add_viewport_btn.on_click = self._on_add_viewport_clicked
        toolbar.add_child(self._add_viewport_btn)

        self._add_rt_btn = Button()
        self._add_rt_btn.text = "+ RT"
        self._add_rt_btn.on_click = lambda: self.render_target_add_requested.emit()
        toolbar.add_child(self._add_rt_btn)

        self.add_child(toolbar)

        self._tree = TreeWidget()
        self._tree.stretch = True
        self._tree.on_select = self._on_tree_select
        self._tree.on_context_menu = self._on_tree_context_menu
        self.add_child(self._tree)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_displays(self, displays: list) -> None:
        self._displays = list(displays)
        self._rebuild_tree()

    def set_display_name(self, display: "Display", name: str) -> None:
        self._display_names[display.tc_display_ptr] = name
        self._rebuild_tree()

    def get_display_name(self, display: "Display") -> str:
        if display.tc_display_ptr in self._display_names:
            return self._display_names[display.tc_display_ptr]
        idx = self._displays.index(display) if display in self._displays else 0
        return f"Display {idx}"

    def add_display(self, display: "Display", name: str | None = None) -> None:
        if display not in self._displays:
            self._displays.append(display)
            if name is not None:
                self._display_names[display.tc_display_ptr] = name
            self._rebuild_tree()

    def remove_display(self, display: "Display") -> None:
        if display in self._displays:
            self._displays.remove(display)
            self._display_names.pop(display.tc_display_ptr, None)
            self._rebuild_tree()

    def set_render_targets(self, render_targets) -> None:
        self._render_targets = list(render_targets or [])
        self._rebuild_tree()

    def refresh(self) -> None:
        self._rebuild_tree()

    # ------------------------------------------------------------------
    # Tree build
    # ------------------------------------------------------------------

    def _rebuild_tree(self) -> None:
        for node in list(self._tree.root_nodes):
            self._tree.remove_root(node)

        for display in self._displays:
            if not self._is_display_valid(display):
                continue
            display_name = self.get_display_name(display)
            display_node = self._make_node(display_name, _NodeKind.DISPLAY, display)

            for i, viewport in enumerate(display.viewports):
                vp_name = viewport.name or f"Viewport {i}"
                camera_name = "No Camera"
                camera = viewport.camera
                if camera is not None:
                    entity = camera.entity
                    if entity is not None:
                        camera_name = entity.name or f"Camera {i}"
                    else:
                        camera_name = f"Camera {i}"

                vp_node = self._make_node(
                    f"{vp_name} ({camera_name})",
                    _NodeKind.VIEWPORT,
                    viewport,
                )
                vp_node.expanded = True

                internal = viewport.internal_entities
                if internal is not None:
                    self._add_entity_hierarchy(vp_node, internal)

                display_node.add_node(vp_node)

            display_node.expanded = True
            self._tree.add_root(display_node)

        if self._render_targets:
            rt_group = self._make_node("Render Targets", _NodeKind.RENDER_TARGET_GROUP)
            for rt in self._render_targets:
                rt_name = rt.name or "RenderTarget"
                rt_node = self._make_node(rt_name, _NodeKind.RENDER_TARGET, rt)
                rt_group.add_node(rt_node)
            rt_group.expanded = True
            self._tree.add_root(rt_group)

    def _is_display_valid(self, display) -> bool:
        try:
            _ = display.tc_display_ptr
            return True
        except Exception:
            return False

    def _make_node(self, text: str, kind: str, obj: object | None = None) -> TreeNode:
        lbl = Label()
        lbl.text = text
        node = TreeNode(lbl)
        node.data = _NodePayload(kind, obj)
        return node

    def _add_entity_hierarchy(self, parent_node: TreeNode, entity: "Entity") -> None:
        if not entity.valid():
            return
        entity_name = entity.name or f"Entity ({entity.uuid[:8]})"
        entity_node = self._make_node(entity_name, _NodeKind.ENTITY, entity)
        entity_node.expanded = True
        parent_node.add_node(entity_node)

        for child_tf in entity.transform.children:
            child_entity = child_tf.entity
            if child_entity is not None and child_entity.valid():
                self._add_entity_hierarchy(entity_node, child_entity)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _get_payload(self, node: TreeNode | None) -> _NodePayload | None:
        if node is None:
            return None
        data = node.data
        if isinstance(data, _NodePayload):
            return data
        return None

    def _on_tree_select(self, node: TreeNode | None) -> None:
        payload = self._get_payload(node)

        if payload is None:
            self.display_selected.emit(None)
            self.viewport_selected.emit(None)
            self.entity_selected.emit(None)
            self.render_target_selected.emit(None)
            return

        if payload.kind == _NodeKind.ENTITY:
            ent = payload.obj
            if ent is not None and ent.valid():
                self.entity_selected.emit(ent)
            else:
                self.entity_selected.emit(None)
        elif payload.kind == _NodeKind.RENDER_TARGET:
            self.render_target_selected.emit(payload.obj)
        elif payload.kind == _NodeKind.VIEWPORT:
            self.viewport_selected.emit(payload.obj)
            self.entity_selected.emit(None)
        elif payload.kind == _NodeKind.DISPLAY:
            self.display_selected.emit(payload.obj)
            self.viewport_selected.emit(None)
            self.entity_selected.emit(None)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _find_parent_node(self, target: TreeNode) -> TreeNode | None:
        for root in self._tree.root_nodes:
            if root is target:
                return None
            found = self._find_parent_recursive(root, target)
            if found is not None:
                return found
        return None

    def _find_parent_recursive(self, node: TreeNode, target: TreeNode) -> TreeNode | None:
        for child in node.subnodes:
            if child is target:
                return node
            found = self._find_parent_recursive(child, target)
            if found is not None:
                return found
        return None

    def _on_tree_context_menu(self, node: TreeNode | None, x: float, y: float) -> None:
        payload = self._get_payload(node)
        items: list[MenuItem] = [
            MenuItem("Add Display", on_click=lambda: self.display_add_requested.emit()),
        ]

        if payload is not None:
            if payload.kind == _NodeKind.DISPLAY:
                display = payload.obj
                items.append(MenuItem.sep())
                items.append(MenuItem(
                    "Add Viewport",
                    on_click=lambda d=display: self.viewport_add_requested.emit(d),
                ))
                items.append(MenuItem(
                    "Remove Display",
                    on_click=lambda d=display: self.display_remove_requested.emit(d),
                ))
            elif payload.kind == _NodeKind.VIEWPORT:
                viewport = payload.obj
                items.append(MenuItem.sep())
                items.append(MenuItem(
                    "Rename...",
                    on_click=lambda v=viewport: self._rename_viewport(v),
                ))
                parent_node = self._find_parent_node(node) if node is not None else None
                parent_payload = self._get_payload(parent_node)
                if parent_payload is not None and parent_payload.kind == _NodeKind.DISPLAY:
                    items.append(MenuItem(
                        "Add Viewport",
                        on_click=lambda d=parent_payload.obj: self.viewport_add_requested.emit(d),
                    ))
                items.append(MenuItem(
                    "Remove Viewport",
                    on_click=lambda v=viewport: self.viewport_remove_requested.emit(v),
                ))
            elif payload.kind == _NodeKind.RENDER_TARGET:
                rt = payload.obj
                items.append(MenuItem.sep())
                items.append(MenuItem(
                    "Rename...",
                    on_click=lambda r=rt: self._rename_render_target(r),
                ))
                items.append(MenuItem(
                    "Remove Render Target",
                    on_click=lambda r=rt: self.render_target_remove_requested.emit(r),
                ))
            elif payload.kind == _NodeKind.RENDER_TARGET_GROUP:
                items.append(MenuItem.sep())
                items.append(MenuItem(
                    "Add Render Target",
                    on_click=lambda: self.render_target_add_requested.emit(),
                ))

        self._ctx_menu.items = items
        if self._tree._ui is not None:
            self._ctx_menu.show(self._tree._ui, x, y)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _on_add_viewport_clicked(self) -> None:
        display = self._get_selected_display()
        if display is not None:
            self.viewport_add_requested.emit(display)

    def _get_selected_display(self) -> "Display | None":
        node = self._tree.selected_node
        if node is None:
            return None
        payload = self._get_payload(node)
        if payload is None:
            return None
        if payload.kind == _NodeKind.DISPLAY:
            return payload.obj
        if payload.kind == _NodeKind.VIEWPORT:
            parent = self._find_parent_node(node)
            parent_payload = self._get_payload(parent)
            if parent_payload is not None and parent_payload.kind == _NodeKind.DISPLAY:
                return parent_payload.obj
        return None

    # ------------------------------------------------------------------
    # Rename dialogs
    # ------------------------------------------------------------------

    def _rename_viewport(self, viewport: "Viewport") -> None:
        ui = self._tree._ui
        if ui is None:
            return
        show_input_dialog(
            ui,
            title="Rename Viewport",
            message="Viewport name:",
            default=viewport.name or "",
            on_result=lambda new_name, v=viewport: self._apply_viewport_rename(v, new_name),
        )

    def _apply_viewport_rename(self, viewport: "Viewport", new_name: str | None) -> None:
        if new_name is None:
            return
        new_name = new_name.strip()
        if not new_name or new_name == (viewport.name or ""):
            return
        viewport.name = new_name
        self.viewport_renamed.emit(viewport, new_name)
        self._rebuild_tree()

    def _rename_render_target(self, render_target) -> None:
        ui = self._tree._ui
        if ui is None:
            return
        show_input_dialog(
            ui,
            title="Rename Render Target",
            message="Render target name:",
            default=render_target.name or "",
            on_result=lambda new_name, rt=render_target: self._apply_rt_rename(rt, new_name),
        )

    def _apply_rt_rename(self, render_target, new_name: str | None) -> None:
        if new_name is None:
            return
        new_name = new_name.strip()
        if not new_name or new_name == (render_target.name or ""):
            return
        render_target.name = new_name
        self._rebuild_tree()
