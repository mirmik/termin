"""Shared tcgui controls for editing procedural CSG documents."""

from __future__ import annotations

from typing import Callable

from tcbase import log
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.panel import Panel
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack

from termin.csg.csg_editor_panel_common import clear_children, make_button, set_visible
from termin.csg.document_tree_model import document_summary
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController
from termin.csg.csg_operation_params_panel import CsgOperationParamsPanel
from termin.csg.operation_specs import (
    ordered_boolean_operation_specs,
    ordered_primitive_specs,
    primitive_label,
)
from termin.csg.csg_primitive_params_panel import CsgPrimitiveParamsPanel
from termin.csg.csg_sketch_params_panel import CsgContourParamsPanel, CsgPlaneParamsPanel
from termin.csg.procedural_document import CONTOUR_ROLE_OUTER


ApplyResultCallback = Callable[[CsgEditorCommandResult, str], bool]


class CsgEditorPanel:
    """Reusable tcgui side panel bound to a ``CsgEditorController``."""

    def __init__(
        self,
        controller: CsgEditorController,
        apply_result: ApplyResultCallback,
        *,
        log_prefix: str,
        fit_callback: Callable[[], None] | None = None,
        clear_callback: Callable[[], None] | None = None,
        request_layout: Callable[[], None] | None = None,
        wireframe_getter: Callable[[], bool] | None = None,
        wireframe_setter: Callable[[bool], None] | None = None,
    ) -> None:
        self.controller = controller
        self._apply_result_callback = apply_result
        self._log_prefix = log_prefix
        self._fit_callback = fit_callback
        self._clear_callback = clear_callback
        self._request_layout_callback = request_layout
        self._wireframe_getter = wireframe_getter
        self._wireframe_setter = wireframe_setter

        self.mode_label = Label()
        self.summary_label = Label()
        self.selection_label = Label()
        self.status_label = Label()
        self.wireframe_checkbox = Checkbox()

        self.context_actions_panel = Panel()
        self.operation_params = CsgOperationParamsPanel(
            self.controller,
            self._dispatch_result,
            self._request_layout,
            log_prefix=self._log_prefix,
        )
        self.primitive_params = CsgPrimitiveParamsPanel(
            self.controller,
            self._dispatch_result,
            self._request_layout,
            log_prefix=self._log_prefix,
        )
        self.plane_params = CsgPlaneParamsPanel(
            self.controller,
            self._dispatch_result,
            self._request_layout,
            log_prefix=self._log_prefix,
        )
        self.contour_params = CsgContourParamsPanel(
            self.controller,
            self._dispatch_result,
            self._request_layout,
            log_prefix=self._log_prefix,
        )

        self.operation_params_panel = self.operation_params.panel
        self.operation_params_title = self.operation_params.title
        self.operation_params_kind = self.operation_params.kind_label
        self.extrude_vector_inputs = self.operation_params.extrude_vector_inputs
        self.wall_param_inputs = self.operation_params.wall_param_inputs
        self.wall_alignment_label = self.operation_params.wall_alignment_label
        self.operation_transform_inputs = self.operation_params.transform_inputs

        self.primitive_params_panel = self.primitive_params.panel
        self.primitive_params_title = self.primitive_params.title
        self.primitive_param_inputs = self.primitive_params.param_inputs
        self.primitive_bool_inputs = self.primitive_params.bool_inputs

        self.plane_params_panel = self.plane_params.panel
        self.plane_params_title = self.plane_params.title
        self.plane_inputs = self.plane_params.inputs

        self.contour_params_panel = self.contour_params.panel
        self.contour_point_inputs = self.contour_params.point_inputs

    @property
    def document(self):
        return self.controller.document

    @property
    def selection(self) -> tuple[str, str] | None:
        return self.controller.selection

    def build(self):
        root = VStack()
        root.spacing = 6

        self.mode_label.text = self._mode_text()
        self.mode_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.mode_label)

        row = HStack()
        row.spacing = 4
        row.preferred_height = px(28)
        row.add_child(make_button("Draw Sketch", self.start_draw_sketch))
        row.add_child(make_button("Close Contour", self.close_contour))
        row.add_child(make_button("Finish Path", self.finish_wall_path))
        root.add_child(row)

        row2 = HStack()
        row2.spacing = 4
        row2.preferred_height = px(28)
        if self._fit_callback is not None:
            row2.add_child(make_button("Fit", self._fit_callback))
        row2.add_child(make_button("Clear", self.clear_document))
        row2.add_child(make_button("Clear Tool", self.clear_tool))
        root.add_child(row2)

        row3 = HStack()
        row3.spacing = 4
        row3.preferred_height = px(28)
        for spec in ordered_boolean_operation_specs():
            row3.add_child(make_button(spec.label, lambda k=spec.kind: self.add_boolean_operation(k)))
        root.add_child(row3)

        primitive_row = HStack()
        primitive_row.spacing = 4
        primitive_row.preferred_height = px(28)
        for spec in ordered_primitive_specs():
            primitive_row.add_child(make_button(spec.label, lambda k=spec.kind: self.add_primitive(k)))
        root.add_child(primitive_row)

        if self._wireframe_getter is not None and self._wireframe_setter is not None:
            view_row = HStack()
            view_row.spacing = 4
            view_row.preferred_height = px(24)
            self.wireframe_checkbox.text = "Wireframe"
            self.wireframe_checkbox.checked = self._wireframe_getter()
            self.wireframe_checkbox.on_changed = self._on_wireframe_changed
            view_row.add_child(self.wireframe_checkbox)
            root.add_child(view_row)

        self.summary_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.summary_label)

        self.selection_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.selection_label)

        self.status_label.text = "Status: Ready"
        self.status_label.color = (0.58, 0.64, 0.72, 1.0)
        root.add_child(self.status_label)

        root.add_child(self.build_context_actions_panel())
        root.add_child(self.operation_params.build())
        root.add_child(self.primitive_params.build())
        root.add_child(self.plane_params.build())
        root.add_child(self.contour_params.build())
        self.refresh_all()
        return root

    def refresh_all(self) -> None:
        self.refresh_labels()
        self.rebuild_context_actions_panel()
        self.operation_params.refresh()
        self.primitive_params.refresh()
        self.plane_params.refresh()
        self.contour_params.refresh()

    def refresh_labels(self) -> None:
        self.mode_label.text = self._mode_text()
        self.summary_label.text = document_summary(self.document)
        if self.selection is None:
            self.selection_label.text = "Selection: <none>"
        else:
            self.selection_label.text = f"Selection: {self.selection[0]} {self.selection[1][:10]}"
        if self._wireframe_getter is not None:
            self.wireframe_checkbox.checked = self._wireframe_getter()

    def set_status(self, text: str) -> None:
        self.status_label.text = f"Status: {text}"

    def build_context_actions_panel(self) -> Panel:
        clear_children(self.context_actions_panel)
        self.context_actions_panel.padding = 8
        self.context_actions_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.context_actions_panel.visible = False
        return self.context_actions_panel

    def rebuild_context_actions_panel(self) -> None:
        clear_children(self.context_actions_panel)
        actions = self._context_actions()
        if not actions:
            self._set_context_actions_visible(False)
            return

        body = VStack()
        body.spacing = 5
        title = Label()
        title.text = "Actions"
        title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(title)
        for label, callback in actions:
            row = HStack()
            row.spacing = 4
            row.preferred_height = px(28)
            row.add_child(make_button(label, callback))
            body.add_child(row)
        self.context_actions_panel.add_child(body)
        self._set_context_actions_visible(True)

    def build_operation_params_panel(self) -> Panel:
        return self.operation_params.build()

    def refresh_operation_params_panel(self) -> None:
        self.operation_params.refresh()

    def build_primitive_params_panel(self) -> Panel:
        return self.primitive_params.build()

    def refresh_primitive_params_panel(self) -> None:
        self.primitive_params.refresh()

    def build_plane_params_panel(self) -> Panel:
        return self.plane_params.build()

    def refresh_plane_params_panel(self) -> None:
        self.plane_params.refresh()

    def build_contour_params_panel(self) -> Panel:
        return self.contour_params.build()

    def refresh_contour_params_panel(self) -> None:
        self.contour_params.refresh()

    def start_draw_sketch(self) -> None:
        result = self.controller.start_draw_sketch()
        self._dispatch_result(result)
        log.info(f"{self._log_prefix} mode=draw_sketch")

    def start_add_outer_contour(self) -> None:
        result = self.controller.start_add_outer_contour()
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} add outer contour started sketch='{self.controller.draft.sketch_id}'")

    def start_add_hole_contour(self) -> None:
        result = self.controller.start_add_hole_contour()
        if not self._dispatch_result(result):
            return
        log.info(
            f"{self._log_prefix} add hole contour started "
            f"sketch='{self.controller.draft.sketch_id}' outer='{self.controller.draft.parent_contour_id}'"
        )

    def start_add_wall_path(self) -> None:
        result = self.controller.start_add_wall_path()
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} add wall path started sketch='{self.controller.draft.sketch_id}'")

    def close_contour(self) -> None:
        result = self.controller.close_contour()
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} contour closed selection='{self.selection}'")

    def finish_wall_path(self) -> None:
        result = self.controller.finish_wall_path()
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} wall path finished selection='{self.selection}'")

    def extrude_selected(self) -> None:
        previous_selection = self.selection
        result = self.controller.extrude_selected()
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} extrude added selection='{self.selection}' previous='{previous_selection}'")

    def wall_selected(self) -> None:
        previous_selection = self.selection
        result = self.controller.wall_selected()
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} wall added selection='{self.selection}' previous='{previous_selection}'")

    def add_boolean_operation(self, kind: str) -> None:
        result = self.controller.add_boolean_operation(kind)
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} boolean added kind='{kind}' selection='{self.selection}'")

    def add_primitive(self, kind: str) -> None:
        result = self.controller.add_primitive(kind)
        if not self._dispatch_result(result, default_status=f"{primitive_label(kind)} added"):
            return
        log.info(f"{self._log_prefix} primitive added kind='{kind}' selection='{self.selection}'")

    def clear_tool(self) -> None:
        result = self.controller.cancel_current_tool()
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} tool cleared")

    def clear_document(self) -> None:
        if self._clear_callback is not None:
            self._clear_callback()
            return
        result = self.controller.new_document()
        self._dispatch_result(result, default_status="Cleared")
        log.info(f"{self._log_prefix} document cleared")

    def set_wall_alignment(self, alignment: str) -> None:
        self.operation_params.set_wall_alignment(alignment)

    def sync_contour_point_inputs(self, point_index: int, point: tuple[float, float]) -> None:
        self.contour_params.sync_point_inputs(point_index, point)

    def _dispatch_result(self, result: CsgEditorCommandResult, default_status: str = "") -> bool:
        ok = self._apply_result_callback(result, default_status)
        if not ok:
            if result.message:
                self.set_status(result.message)
            return False
        status = result.message if result.message else default_status
        if status:
            self.set_status(status)
        return True

    def _context_actions(self):
        if self.selection is None:
            return []
        kind, item_id = self.selection
        if kind == "sketch":
            if self.document.find_sketch(item_id) is None:
                return []
            return [
                ("Add Outer Contour", self.start_add_outer_contour),
                ("Add Wall Path", self.start_add_wall_path),
                ("Wall", self.wall_selected),
                ("Extrude Sketch", self.extrude_selected),
            ]
        if kind == "path":
            path_ref = self.document.find_path_ref(item_id)
            if path_ref is None:
                return []
            return []
        if kind == "contour":
            contour_ref = self.document.find_contour_ref(item_id)
            if contour_ref is None:
                return []
            _sketch, contour = contour_ref
            if contour.role == CONTOUR_ROLE_OUTER:
                return [("Add Hole", self.start_add_hole_contour)]
        return []

    def _on_wireframe_changed(self, checked: bool) -> None:
        if self._wireframe_setter is not None:
            self._wireframe_setter(bool(checked))

    def _set_context_actions_visible(self, visible: bool) -> None:
        set_visible(self.context_actions_panel, visible, self._request_layout)

    def _request_layout(self) -> None:
        if self._request_layout_callback is not None:
            self._request_layout_callback()
            return
        if self.operation_params_panel._ui is not None:
            self.operation_params_panel._ui.request_layout()

    def _mode_text(self) -> str:
        return f"Mode: {self.controller.mode}; draft points: {len(self.controller.draft.points)}"


__all__ = ["CsgEditorPanel"]
