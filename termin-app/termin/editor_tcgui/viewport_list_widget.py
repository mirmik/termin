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

from termin.editor_core.viewport_list_model import (
    ViewportListController,
    ViewportListNode,
    ViewportNodeKind,
)

if TYPE_CHECKING:
    from termin.display import Display
    from termin.viewport import Viewport


class _NodeKind:
    DISPLAY = ViewportNodeKind.DISPLAY
    VIEWPORT = ViewportNodeKind.VIEWPORT
    ENTITY = ViewportNodeKind.ENTITY
    RENDER_TARGET_GROUP = ViewportNodeKind.RENDER_TARGET_GROUP
    RENDER_TARGET = ViewportNodeKind.RENDER_TARGET


class _NodePayload:
    kind: str
    obj: object | None
    stable_id: str | None

    def __init__(
        self,
        kind: str,
        obj: object | None = None,
        stable_id: str | None = None,
    ):
        self.kind = kind
        self.obj = obj
        self.stable_id = stable_id


class ViewportListWidgetTcgui(VStack):
    """Displays a Display → Viewport → Entity tree plus a Render Targets section.

    RenderingController wires selection / add / remove signals through
    editor_core.Signal instances.
    """

    def __init__(self):
        super().__init__()
        self.spacing = 4

        self._controller = ViewportListController()

        self._ui = None
        self._ctx_menu = Menu()

        self.display_selected = self._controller.display_selected
        self.viewport_selected = self._controller.viewport_selected
        self.entity_selected = self._controller.entity_selected
        self.render_target_selected = self._controller.render_target_selected
        self.display_add_requested = self._controller.display_add_requested
        self.viewport_add_requested = self._controller.viewport_add_requested
        self.display_remove_requested = self._controller.display_remove_requested
        self.viewport_remove_requested = self._controller.viewport_remove_requested
        self.viewport_renamed = self._controller.viewport_renamed
        self.render_target_add_requested = self._controller.render_target_add_requested
        self.render_target_remove_requested = self._controller.render_target_remove_requested
        self._controller.snapshot_changed.connect(self._rebuild_tree)

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
        self._add_display_btn.on_click = self._controller.request_add_display
        toolbar.add_child(self._add_display_btn)

        self._add_viewport_btn = Button()
        self._add_viewport_btn.text = "+ Viewport"
        self._add_viewport_btn.on_click = self._on_add_viewport_clicked
        toolbar.add_child(self._add_viewport_btn)

        self._add_rt_btn = Button()
        self._add_rt_btn.text = "+ RT"
        self._add_rt_btn.on_click = self._controller.request_add_render_target
        toolbar.add_child(self._add_rt_btn)

        self._add_xr_rt_btn = Button()
        self._add_xr_rt_btn.text = "+ XR RT"
        self._add_xr_rt_btn.on_click = lambda: self._controller.request_add_render_target("xr_stereo")
        toolbar.add_child(self._add_xr_rt_btn)

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
        self._controller.set_displays(displays)

    def set_display_name(self, display: "Display", name: str) -> None:
        self._controller.set_display_name(display, name)

    def get_display_name(self, display: "Display") -> str:
        return self._controller.get_display_name(display)

    def add_display(self, display: "Display", name: str | None = None) -> None:
        self._controller.add_display(display, name)

    def remove_display(self, display: "Display") -> None:
        self._controller.remove_display(display)

    def set_render_targets(self, render_targets) -> None:
        self._controller.set_render_targets(render_targets)

    def refresh(self) -> None:
        self._controller.refresh()

    # ------------------------------------------------------------------
    # Tree build
    # ------------------------------------------------------------------

    def _rebuild_tree(self, snapshot=None) -> None:
        snapshot = snapshot or self._controller.snapshot
        for node in list(self._tree.root_nodes):
            self._tree.remove_root(node)
        for root in snapshot.roots:
            self._tree.add_root(self._project_node(root))

    def _project_node(self, source: ViewportListNode) -> TreeNode:
        lbl = Label()
        lbl.text = source.label
        node = TreeNode(lbl)
        node.data = _NodePayload(source.kind, source.value, source.stable_id)
        for child in source.children:
            node.add_node(self._project_node(child))
        node.expanded = bool(source.children)
        return node

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
        self._controller.select(None if payload is None else payload.stable_id)

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
            MenuItem("Add Display", on_click=self._controller.request_add_display),
        ]

        if payload is not None:
            if payload.kind == _NodeKind.DISPLAY:
                display = payload.obj
                items.append(MenuItem.sep())
                items.append(
                    MenuItem(
                        "Add Viewport",
                        on_click=lambda d=display: self._controller.request_add_viewport(d),
                    )
                )
                items.append(
                    MenuItem(
                        "Remove Display",
                        on_click=lambda sid=payload.stable_id: self._controller.request_remove(sid),
                    )
                )
            elif payload.kind == _NodeKind.VIEWPORT:
                viewport = payload.obj
                items.append(MenuItem.sep())
                items.append(
                    MenuItem(
                        "Rename...",
                        on_click=lambda v=viewport: self._rename_viewport(v),
                    )
                )
                parent_node = self._find_parent_node(node) if node is not None else None
                parent_payload = self._get_payload(parent_node)
                if parent_payload is not None and parent_payload.kind == _NodeKind.DISPLAY:
                    items.append(
                        MenuItem(
                            "Add Viewport",
                            on_click=lambda d=parent_payload.obj: self._controller.request_add_viewport(d),
                        )
                    )
                items.append(
                    MenuItem(
                        "Remove Viewport",
                        on_click=lambda sid=payload.stable_id: self._controller.request_remove(sid),
                    )
                )
            elif payload.kind == _NodeKind.RENDER_TARGET:
                rt = payload.obj
                items.append(MenuItem.sep())
                items.append(
                    MenuItem(
                        "Rename...",
                        on_click=lambda r=rt: self._rename_render_target(r),
                    )
                )
                items.append(
                    MenuItem(
                        "Remove Render Target",
                        on_click=lambda sid=payload.stable_id: self._controller.request_remove(sid),
                    )
                )
            elif payload.kind == _NodeKind.RENDER_TARGET_GROUP:
                items.append(MenuItem.sep())
                items.append(
                    MenuItem(
                        "Add Render Target",
                        on_click=self._controller.request_add_render_target,
                    )
                )
                items.append(
                    MenuItem(
                        "Add XR Stereo Target",
                        on_click=lambda: self._controller.request_add_render_target("xr_stereo"),
                    )
                )

        self._ctx_menu.items = items
        if self._tree._ui is not None:
            self._ctx_menu.show(self._tree._ui, x, y)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _on_add_viewport_clicked(self) -> None:
        display = self._get_selected_display()
        self._controller.request_add_viewport(display)

    def _get_selected_display(self) -> "Display | None":
        return self._controller.selected_display()

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
        self._controller.rename(self._controller.viewport_stable_id(viewport), new_name)

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
        self._controller.rename(self._controller.render_target_stable_id(render_target), new_name)
