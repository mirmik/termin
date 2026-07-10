"""tcgui editor extension for ProceduralMeshComponent."""

from __future__ import annotations

from tcbase import log
from tcgui.widgets.label import Label
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.vstack import VStack

from termin.editor_core.component_editor_extension import (
    register_component_editor_extension,
)
from termin.editor_core.procedural_mesh_editor_extension import (
    ProceduralMeshExtensionModel,
)
from termin.csg.cad_tree_adapter import (
    restore_tree_selection,
    to_tree_node,
    tree_node_data,
    tree_node_payload,
)
from termin.csg.csg_editor_panel import CsgEditorPanel
from termin.csg.document_tree_model import (
    build_document_tree,
    document_summary,
)
from termin.csg.editor_controller import CsgEditorCommandResult


class ProceduralMeshEditorExtension:
    def __init__(self) -> None:
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._component = None
        self._model = ProceduralMeshExtensionModel()
        self._controller = self._model.controller
        self._editor_panel = self._create_editor_panel()
        self._document_summary_label = Label()
        self._selection_label = Label()
        self._document_tree = TreeWidget()

    def _create_editor_panel(self) -> CsgEditorPanel:
        return CsgEditorPanel(
            self._controller,
            self._apply_controller_result,
            log_prefix="[ProceduralMeshEditor]",
            clear_callback=self._clear_document,
            request_layout=self._request_layout,
        )

    def attach(self, editor, entity, component_ref) -> None:
        self._editor = editor
        self._entity = entity
        self._component_ref = component_ref
        self._model.attach(editor, entity, component_ref)
        self._component = self._model.component
        self._controller = self._model.controller
        self._model.set_changed_handler(self._on_model_changed)
        log.info("[ProceduralMeshEditor] extension attached")

    def detach(self) -> None:
        self._model.set_changed_handler(None)
        self._model.detach()
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._component = None
        self._controller = self._model.controller
        self._editor_panel = self._create_editor_panel()
        log.info("[ProceduralMeshEditor] extension detached")

    def build_panel(self):
        root = VStack()
        root.spacing = 4

        title = Label()
        title.text = "Procedural Geometry"
        root.add_child(title)
        root.add_child(self._editor_panel.build())

        return root

    def build_left_panel(self):
        root = VStack()
        root.spacing = 4

        title = Label()
        title.text = "Document Tree"
        root.add_child(title)

        self._document_summary_label = Label()
        self._document_summary_label.text = "Document: <empty>"
        self._document_summary_label.color = (0.55, 0.60, 0.68, 1.0)
        root.add_child(self._document_summary_label)

        self._selection_label = Label()
        self._selection_label.text = "Selection: <none>"
        self._selection_label.color = (0.55, 0.60, 0.68, 1.0)
        root.add_child(self._selection_label)

        self._document_tree = TreeWidget()
        self._document_tree.row_height = 22
        self._document_tree.indent_size = 22
        self._document_tree.stretch = True
        self._document_tree.on_select = self._on_document_node_selected
        root.add_child(self._document_tree)
        self._refresh_document_tree()

        return root

    def _set_mode(self, mode: str) -> None:
        if mode == "draw_sketch":
            result = self._controller.start_draw_sketch()
        elif mode == "idle":
            result = self._controller.cancel_current_tool()
        else:
            log.error(f"[ProceduralMeshEditor] unknown mode requested '{mode}'")
            result = CsgEditorCommandResult.failed("Unknown mode")
        if self._apply_controller_result(result):
            log.info(f"[ProceduralMeshEditor] mode={self._controller.mode}")

    def _mode_text(self) -> str:
        return (
            f"Mode: {self._controller.mode}; "
            f"draft points: {len(self._controller.draft.points)}; "
            f"contours: {self._document_contour_count()}"
        )

    def _refresh_mode_label(self) -> None:
        self._editor_panel.refresh_labels()

    def _add_primitive_operation(self, kind: str) -> None:
        if not self._ensure_controller_document():
            return
        result = self._controller.add_primitive(kind)
        if not self._apply_controller_result(result):
            return
        log.info(
            f"[ProceduralMeshEditor] primitive operation added kind='{kind}' selection='{self._controller.selection}'"
        )

    def _add_boolean_operation(self, kind: str) -> None:
        if not self._ensure_controller_document():
            return
        result = self._controller.add_boolean_operation(kind)
        if not self._apply_controller_result(result):
            return
        log.info(
            f"[ProceduralMeshEditor] boolean operation added kind='{kind}' selection='{self._controller.selection}'"
        )

    def _clear_sketch(self) -> None:
        self._clear_document()

    def _clear_document(self) -> None:
        if not self._ensure_controller_document():
            return
        result = self._controller.new_document()
        self._apply_controller_result(result)
        log.info("[ProceduralMeshEditor] sketch cleared")

    def _document_contour_count(self) -> int:
        return self._controller.document.contour_count()

    def _refresh_document_tree(self) -> None:
        self._document_tree.clear()
        component = self._component
        if component is None:
            self._document_summary_label.text = "Document: <no component>"
            self._selection_label.text = "Selection: <none>"
            self._document_tree.add_root(self._tree_node("No component object", ("info", "none")))
            return
        if self._controller.document is not component.document:
            self._controller.replace_document(component.document, self._controller.selection)

        self._document_summary_label.text = document_summary(self._controller.document)
        roots = [to_tree_node(root) for root in build_document_tree(self._controller.document)]

        for node in roots:
            self._document_tree.add_root(node)
        restore_tree_selection(self._document_tree, roots, self._controller.selection)
        self._refresh_selection_label()
        if self._document_tree._ui is not None:
            self._document_tree._ui.request_layout()

    def _tree_node(self, text: str, data: tuple[str, str]) -> TreeNode:
        label = Label()
        label.text = text
        label.color = (0.68, 0.72, 0.78, 1.0)
        node = TreeNode(label)
        node.data = tree_node_payload(data[0], data[1])
        return node

    def _on_document_node_selected(self, node: TreeNode) -> None:
        node_data = tree_node_data(node)
        if node_data is None:
            log.error("[ProceduralMeshEditor] document tree node has invalid selection data")
            return
        self._apply_controller_result(self._controller.select_node(node_data))

    def _refresh_selection_label(self) -> None:
        node_data = self._controller.selection
        if node_data is None:
            self._selection_label.text = "Selection: <none>"
            return
        self._selection_label.text = f"Selection: {node_data[0]} {self._short_id(node_data[1])}"

    def _ensure_controller_document(self) -> bool:
        return self._model.ensure_component_document()

    def _apply_controller_result(
        self,
        result: CsgEditorCommandResult,
        default_status: str = "",
    ) -> bool:
        if not self._model.apply_result(result, default_status):
            return False
        if result.tree_changed or result.selection_changed:
            self._refresh_document_tree()
        else:
            self._refresh_selection_label()
        self._editor_panel.refresh_all()
        status = result.message if result.message else default_status
        if status:
            self._editor_panel.set_status(status)
        return True

    def _short_id(self, value: str) -> str:
        if len(value) <= 10:
            return value
        return value[:10]

    def _request_viewport_update(self) -> None:
        editor = self._editor
        if editor is not None:
            editor.request_viewport_update()

    def _request_layout(self) -> None:
        if self._editor_panel.operation_params_panel._ui is not None:
            self._editor_panel.operation_params_panel._ui.request_layout()

    def _on_model_changed(self, snapshot) -> None:
        self._refresh_document_tree()
        self._editor_panel.refresh_all()
        self._editor_panel.set_status(snapshot.status)

    def _on_viewport_click(self, event) -> bool:
        return self._model.viewport_interaction.on_click(event)

    def _on_viewport_pointer(self, event) -> bool:
        return self._model.viewport_interaction.on_pointer(event)

    def _draw_overlay(self) -> None:
        self._model.viewport_interaction.draw_overlay()


def register_default_extension() -> None:
    register_component_editor_extension(
        "ProceduralMeshComponent",
        ProceduralMeshEditorExtension,
    )


__all__ = ["ProceduralMeshEditorExtension", "register_default_extension"]
