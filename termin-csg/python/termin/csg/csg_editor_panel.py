"""Shared tcgui controls for editing procedural CSG documents."""

from __future__ import annotations

from typing import Callable

from tcbase import log
from tcgui.widgets.button import Button
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.panel import Panel
from tcgui.widgets.separator import Separator
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack

from termin.csg.document_eval import extrude_vector_for_operation
from termin.csg.document_tree_model import document_summary
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController
from termin.csg.operation_specs import (
    BOOLEAN_OPERATION_KINDS,
    PRIMITIVE_OPERATION_KIND,
    OperationParamSpec,
    ordered_boolean_operation_specs,
    ordered_primitive_specs,
    primitive_label,
    primitive_spec,
)
from termin.csg.procedural_document import (
    CONTOUR_ROLE_HOLE,
    CONTOUR_ROLE_OUTER,
    OPERATION_KIND_WALL,
    ProceduralPlane,
)


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
        self.operation_params_panel = Panel()
        self.operation_params_title = Label()
        self.operation_params_kind = Label()
        self.extrude_vector_inputs: dict[str, SpinBox] = {}
        self.wall_param_inputs: dict[str, SpinBox] = {}
        self.wall_alignment_label = Label()
        self.operation_transform_inputs: dict[str, SpinBox] = {}
        self._syncing_operation_params = False

        self.primitive_params_panel = Panel()
        self.primitive_params_title = Label()
        self.primitive_param_inputs: dict[str, SpinBox] = {}
        self.primitive_bool_inputs: dict[str, Checkbox] = {}
        self._syncing_primitive_params = False

        self.plane_params_panel = Panel()
        self.plane_params_title = Label()
        self.plane_inputs: dict[str, SpinBox] = {}
        self._syncing_plane_params = False

        self.contour_params_panel = Panel()
        self.contour_point_inputs: dict[tuple[int, str], SpinBox] = {}
        self._syncing_contour_params = False

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
        row.add_child(self._button("Draw Sketch", self.start_draw_sketch))
        row.add_child(self._button("Close Contour", self.close_contour))
        row.add_child(self._button("Finish Path", self.finish_wall_path))
        root.add_child(row)

        row2 = HStack()
        row2.spacing = 4
        row2.preferred_height = px(28)
        if self._fit_callback is not None:
            row2.add_child(self._button("Fit", self._fit_callback))
        row2.add_child(self._button("Clear", self.clear_document))
        row2.add_child(self._button("Clear Tool", self.clear_tool))
        root.add_child(row2)

        row3 = HStack()
        row3.spacing = 4
        row3.preferred_height = px(28)
        for spec in ordered_boolean_operation_specs():
            row3.add_child(self._button(spec.label, lambda k=spec.kind: self.add_boolean_operation(k)))
        root.add_child(row3)

        primitive_row = HStack()
        primitive_row.spacing = 4
        primitive_row.preferred_height = px(28)
        for spec in ordered_primitive_specs():
            primitive_row.add_child(self._button(spec.label, lambda k=spec.kind: self.add_primitive(k)))
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
        root.add_child(self.build_operation_params_panel())
        root.add_child(self.build_primitive_params_panel())
        root.add_child(self.build_plane_params_panel())
        root.add_child(self.build_contour_params_panel())
        self.refresh_all()
        return root

    def refresh_all(self) -> None:
        self.refresh_labels()
        self.rebuild_context_actions_panel()
        self.refresh_operation_params_panel()
        self.refresh_primitive_params_panel()
        self.refresh_plane_params_panel()
        self.refresh_contour_params_panel()

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
        self._clear_children(self.context_actions_panel)
        self.context_actions_panel.padding = 8
        self.context_actions_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.context_actions_panel.visible = False
        return self.context_actions_panel

    def rebuild_context_actions_panel(self) -> None:
        self._clear_children(self.context_actions_panel)
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
            row.add_child(self._button(label, callback))
            body.add_child(row)
        self.context_actions_panel.add_child(body)
        self._set_context_actions_visible(True)

    def build_operation_params_panel(self) -> Panel:
        self._clear_children(self.operation_params_panel)
        self.extrude_vector_inputs.clear()
        self.wall_param_inputs.clear()
        self.operation_transform_inputs.clear()
        self.operation_params_panel.padding = 8
        self.operation_params_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.operation_params_panel.visible = False
        return self.operation_params_panel

    def refresh_operation_params_panel(self) -> None:
        operation = self._selected_operation()
        if operation is None:
            self._set_operation_params_visible(False)
            return
        if operation.kind == PRIMITIVE_OPERATION_KIND:
            self._set_operation_params_visible(False)
            return
        if operation.kind not in {"extrude", OPERATION_KIND_WALL} and operation.kind not in BOOLEAN_OPERATION_KINDS:
            self._set_operation_params_visible(False)
            return
        if not self._rebuild_operation_params_panel(operation):
            self._set_operation_params_visible(False)
            return
        self._set_operation_params_visible(True)

    def _rebuild_operation_params_panel(self, operation) -> bool:
        self._clear_children(self.operation_params_panel)
        self.extrude_vector_inputs.clear()
        self.wall_param_inputs.clear()
        self.operation_transform_inputs.clear()
        body = VStack()
        body.spacing = 5

        self.operation_params_title.text = operation.name
        self.operation_params_title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(self.operation_params_title)
        self.operation_params_kind.text = f"Kind: {operation.kind}"
        self.operation_params_kind.color = (0.58, 0.64, 0.72, 1.0)
        body.add_child(self.operation_params_kind)
        separator = Separator()
        separator.orientation = "horizontal"
        body.add_child(separator)

        self._syncing_operation_params = True
        if operation.kind == "extrude":
            source_sketch_id = str(operation.params.get("source_sketch_id", ""))
            sketch = self.document.find_sketch(source_sketch_id)
            if sketch is None:
                self._syncing_operation_params = False
                log.error(
                    f"{self._log_prefix} cannot show extrude parameters: "
                    f"source sketch not found '{source_sketch_id}'"
                )
                return False
            vector = extrude_vector_for_operation(sketch, operation)
            vector_label = Label()
            vector_label.text = "Extrude vector"
            vector_label.color = (0.70, 0.74, 0.80, 1.0)
            body.add_child(vector_label)
            for axis in ("x", "y", "z"):
                row = self._build_vector_row(axis)
                self.extrude_vector_inputs[axis].value = vector[("x", "y", "z").index(axis)]
                body.add_child(row)
        if operation.kind == OPERATION_KIND_WALL:
            source_sketch_id = str(operation.params.get("source_sketch_id", ""))
            sketch = self.document.find_sketch(source_sketch_id)
            if sketch is None:
                self._syncing_operation_params = False
                log.error(
                    f"{self._log_prefix} cannot show wall parameters: "
                    f"source sketch not found '{source_sketch_id}'"
                )
                return False
            wall_label = Label()
            wall_label.text = "Wall"
            wall_label.color = (0.70, 0.74, 0.80, 1.0)
            body.add_child(wall_label)
            body.add_child(
                self._build_wall_number_row(
                    "height",
                    "Height",
                    _param_float(operation.params, "height", 3.0),
                    min_value=0.001,
                )
            )
            body.add_child(
                self._build_wall_number_row(
                    "thickness",
                    "Thickness",
                    _param_float(operation.params, "thickness", 0.2),
                    min_value=0.001,
                )
            )
            self.wall_alignment_label.text = f"Alignment: {operation.params.get('alignment', 'center')}"
            self.wall_alignment_label.color = (0.58, 0.64, 0.72, 1.0)
            body.add_child(self.wall_alignment_label)
            alignment_row = HStack()
            alignment_row.spacing = 4
            alignment_row.preferred_height = px(28)
            alignment_row.add_child(self._button("Center", lambda: self.set_wall_alignment("center")))
            alignment_row.add_child(self._button("Left", lambda: self.set_wall_alignment("left")))
            alignment_row.add_child(self._button("Right", lambda: self.set_wall_alignment("right")))
            body.add_child(alignment_row)

        self._append_operation_transform_rows(body, "center", "Center", operation.params)
        self._append_operation_transform_rows(body, "rotation", "Rotation", operation.params)
        self._syncing_operation_params = False
        self.operation_params_panel.add_child(body)
        return True

    def build_primitive_params_panel(self) -> Panel:
        self._clear_children(self.primitive_params_panel)
        self.primitive_param_inputs.clear()
        self.primitive_bool_inputs.clear()
        self.primitive_params_panel.padding = 8
        self.primitive_params_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.primitive_params_panel.visible = False
        return self.primitive_params_panel

    def refresh_primitive_params_panel(self) -> None:
        operation = self._selected_primitive_operation()
        if operation is None:
            self._set_primitive_params_visible(False)
            return
        self._rebuild_primitive_params_panel(operation)
        self._set_primitive_params_visible(True)

    def _rebuild_primitive_params_panel(self, operation) -> None:
        self._clear_children(self.primitive_params_panel)
        self.primitive_param_inputs.clear()
        self.primitive_bool_inputs.clear()
        body = VStack()
        body.spacing = 5

        primitive_kind = str(operation.params.get("primitive_kind", ""))
        spec = primitive_spec(primitive_kind)
        self.primitive_params_title.text = f"{primitive_label(primitive_kind)}: {operation.name}"
        self.primitive_params_title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(self.primitive_params_title)
        separator = Separator()
        separator.orientation = "horizontal"
        body.add_child(separator)

        self._syncing_primitive_params = True
        if spec is None:
            log.error(f"{self._log_prefix} cannot build primitive params: unknown primitive kind '{primitive_kind}'")
        else:
            self._append_primitive_schema_rows(body, spec.param_schema, operation.params)
        self._syncing_primitive_params = False
        self.primitive_params_panel.add_child(body)

    def build_plane_params_panel(self) -> Panel:
        self._clear_children(self.plane_params_panel)
        self.plane_inputs.clear()
        self.plane_params_panel.padding = 8
        self.plane_params_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.plane_params_panel.visible = False

        body = VStack()
        body.spacing = 5
        self.plane_params_title.text = "Plane"
        self.plane_params_title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(self.plane_params_title)
        separator = Separator()
        separator.orientation = "horizontal"
        body.add_child(separator)
        for group, label_text in (
            ("origin", "Origin"),
            ("x_axis", "X axis"),
            ("y_axis", "Y axis"),
        ):
            label = Label()
            label.text = label_text
            label.color = (0.70, 0.74, 0.80, 1.0)
            body.add_child(label)
            for axis in ("x", "y", "z"):
                body.add_child(self._build_plane_vector_row(group, axis))
        self.plane_params_panel.add_child(body)
        return self.plane_params_panel

    def refresh_plane_params_panel(self) -> None:
        sketch = self._selected_plane_sketch()
        if sketch is None:
            self._set_plane_params_visible(False)
            return
        self.plane_params_title.text = f"Plane: {sketch.name}"
        self._syncing_plane_params = True
        self._set_plane_input_vec("origin", sketch.plane.origin)
        self._set_plane_input_vec("x_axis", sketch.plane.x_axis)
        self._set_plane_input_vec("y_axis", sketch.plane.y_axis)
        self._syncing_plane_params = False
        self._set_plane_params_visible(True)

    def build_contour_params_panel(self) -> Panel:
        self._clear_children(self.contour_params_panel)
        self.contour_point_inputs.clear()
        self.contour_params_panel.padding = 8
        self.contour_params_panel.background_color = (0.10, 0.105, 0.12, 1.0)
        self.contour_params_panel.visible = False
        return self.contour_params_panel

    def refresh_contour_params_panel(self) -> None:
        contour_ref = self._selected_contour_ref()
        if contour_ref is None:
            self._set_contour_params_visible(False)
            return
        _sketch, contour = contour_ref
        self._rebuild_contour_params_panel(contour)
        self._set_contour_params_visible(True)

    def _rebuild_contour_params_panel(self, contour) -> None:
        self._clear_children(self.contour_params_panel)
        self.contour_point_inputs.clear()
        body = VStack()
        body.spacing = 5

        title = Label()
        title.text = f"{_contour_role_label(contour.role)}: {contour.name}"
        title.color = (0.84, 0.88, 0.94, 1.0)
        body.add_child(title)
        role_label = Label()
        role_label.text = self._contour_role_text(contour)
        role_label.color = (0.58, 0.64, 0.72, 1.0)
        body.add_child(role_label)
        hint = Label()
        hint.text = "Local points"
        hint.color = (0.58, 0.64, 0.72, 1.0)
        body.add_child(hint)
        separator = Separator()
        separator.orientation = "horizontal"
        body.add_child(separator)

        self._syncing_contour_params = True
        for index, point in enumerate(contour.points):
            row = self._build_contour_point_row(index)
            self.contour_point_inputs[(index, "x")].value = point[0]
            self.contour_point_inputs[(index, "y")].value = point[1]
            body.add_child(row)
        self._syncing_contour_params = False
        self.contour_params_panel.add_child(body)

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
        if self._syncing_operation_params:
            return
        self._apply_wall_params_from_inputs(alignment=alignment)

    def sync_contour_point_inputs(self, point_index: int, point: tuple[float, float]) -> None:
        x_key = (point_index, "x")
        y_key = (point_index, "y")
        if x_key not in self.contour_point_inputs or y_key not in self.contour_point_inputs:
            return
        self._syncing_contour_params = True
        try:
            self.contour_point_inputs[x_key].value = point[0]
            self.contour_point_inputs[y_key].value = point[1]
        finally:
            self._syncing_contour_params = False

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

    def _selected_operation(self):
        if self.selection is None:
            return None
        kind, item_id = self.selection
        if kind != "operation":
            return None
        return self.document.find_operation(item_id)

    def _selected_primitive_operation(self):
        operation = self._selected_operation()
        if operation is None or operation.kind != PRIMITIVE_OPERATION_KIND:
            return None
        return operation

    def _selected_plane_sketch(self):
        if self.selection is None:
            return None
        kind, item_id = self.selection
        if kind != "plane":
            return None
        return self.document.find_sketch(item_id)

    def _selected_contour_ref(self):
        if self.selection is None:
            return None
        kind, item_id = self.selection
        if kind != "contour":
            return None
        return self.document.find_contour_ref(item_id)

    def _contour_role_text(self, contour) -> str:
        if contour.role != CONTOUR_ROLE_HOLE:
            return "Role: Outer"
        parent_ref = self.document.find_contour_ref(str(contour.parent_contour_id or ""))
        if parent_ref is None:
            return f"Role: Hole; parent: <missing {contour.parent_contour_id}>"
        _sketch, parent = parent_ref
        return f"Role: Hole; parent: {parent.name}"

    def _button(self, text: str, callback) -> Button:
        button = Button()
        button.text = text
        button.on_click = callback
        return button

    def _build_vector_row(self, axis: str) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)
        label = Label()
        label.text = axis.upper()
        label.color = (0.58, 0.64, 0.72, 1.0)
        label.preferred_width = px(18)
        row.add_child(label)
        spin = SpinBox()
        spin.decimals = 3
        spin.step = 0.1
        spin.min_value = -1000000.0
        spin.max_value = 1000000.0
        spin.preferred_height = px(24)
        spin.stretch = True
        spin.on_changed = self._on_extrude_vector_changed
        self.extrude_vector_inputs[axis] = spin
        row.add_child(spin)
        return row

    def _build_wall_number_row(
        self,
        key: str,
        label_text: str,
        value: float,
        min_value: float = -1000000.0,
    ) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)
        label = Label()
        label.text = label_text
        label.color = (0.58, 0.64, 0.72, 1.0)
        label.preferred_width = px(82)
        row.add_child(label)
        spin = SpinBox()
        spin.decimals = 3
        spin.step = 0.1
        spin.min_value = min_value
        spin.max_value = 1000000.0
        spin.preferred_height = px(24)
        spin.stretch = True
        spin.value = value
        spin.on_changed = self._on_wall_param_changed
        self.wall_param_inputs[key] = spin
        row.add_child(spin)
        return row

    def _append_operation_transform_rows(self, body: VStack, group: str, label_text: str, params: dict) -> None:
        label = Label()
        label.text = label_text
        label.color = (0.70, 0.74, 0.80, 1.0)
        body.add_child(label)
        value = _param_vec3(params, group, (0.0, 0.0, 0.0))
        for index, axis in enumerate(("x", "y", "z")):
            key = f"{group}.{axis}"
            row = HStack()
            row.spacing = 6
            row.preferred_height = px(26)
            axis_label = Label()
            axis_label.text = axis.upper()
            axis_label.color = (0.58, 0.64, 0.72, 1.0)
            axis_label.preferred_width = px(18)
            row.add_child(axis_label)
            spin = SpinBox()
            spin.decimals = 3
            spin.step = 0.1
            spin.min_value = -1000000.0
            spin.max_value = 1000000.0
            spin.preferred_height = px(24)
            spin.stretch = True
            spin.value = value[index]
            spin.on_changed = self._on_operation_transform_changed
            self.operation_transform_inputs[key] = spin
            row.add_child(spin)
            body.add_child(row)

    def _append_primitive_schema_rows(
        self,
        body: VStack,
        param_schema: tuple[OperationParamSpec, ...],
        params: dict,
    ) -> None:
        for param in param_schema:
            if param.kind == "vec3":
                default_vec = _param_vec3({"value": param.default}, "value", (0.0, 0.0, 0.0))
                min_value = -1000000.0 if param.min_value is None else float(param.min_value)
                self._append_primitive_vector_rows(
                    body,
                    param.key,
                    param.label,
                    params,
                    default_vec,
                    min_value=min_value,
                )
            elif param.kind == "bool":
                self._append_primitive_bool_row(body, param.key, param.label, params, bool(param.default))
            elif param.kind == "int":
                body.add_child(
                    self._build_primitive_number_row(
                        param.key,
                        param.label,
                        params,
                        float(param.default),
                        decimals=0,
                        step=1.0,
                        min_value=-1000000.0 if param.min_value is None else float(param.min_value),
                        max_value=1000000.0 if param.max_value is None else float(param.max_value),
                    )
                )
            elif param.kind == "float":
                body.add_child(
                    self._build_primitive_number_row(
                        param.key,
                        param.label,
                        params,
                        float(param.default),
                        min_value=-1000000.0 if param.min_value is None else float(param.min_value),
                        max_value=1000000.0 if param.max_value is None else float(param.max_value),
                    )
                )
            else:
                log.error(f"{self._log_prefix} unsupported primitive param kind '{param.kind}' key='{param.key}'")

    def _append_primitive_vector_rows(
        self,
        body: VStack,
        group: str,
        label_text: str,
        params: dict,
        default: tuple[float, float, float],
        min_value: float = -1000000.0,
    ) -> None:
        label = Label()
        label.text = label_text
        label.color = (0.70, 0.74, 0.80, 1.0)
        body.add_child(label)
        value = _param_vec3(params, group, default)
        for index, axis in enumerate(("x", "y", "z")):
            key = f"{group}.{axis}"
            row = self._build_primitive_number_row(
                key,
                axis.upper(),
                {},
                value[index],
                min_value=min_value,
                label_width=18,
            )
            body.add_child(row)

    def _build_primitive_number_row(
        self,
        key: str,
        label_text: str,
        params: dict,
        default: float,
        decimals: int = 3,
        step: float = 0.1,
        min_value: float = -1000000.0,
        max_value: float = 1000000.0,
        label_width: int = 82,
    ) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)
        label = Label()
        label.text = label_text
        label.color = (0.58, 0.64, 0.72, 1.0)
        label.preferred_width = px(label_width)
        row.add_child(label)
        spin = SpinBox()
        spin.decimals = decimals
        spin.step = step
        spin.min_value = min_value
        spin.max_value = max_value
        spin.preferred_height = px(24)
        spin.stretch = True
        spin.value = float(params.get(key, default))
        spin.on_changed = self._on_primitive_param_changed
        self.primitive_param_inputs[key] = spin
        row.add_child(spin)
        return row

    def _append_primitive_bool_row(self, body: VStack, key: str, label_text: str, params: dict, default: bool) -> None:
        row = HStack()
        row.spacing = 4
        row.preferred_height = px(24)
        checkbox = Checkbox()
        checkbox.text = label_text
        checkbox.checked = bool(params.get(key, default))
        checkbox.on_changed = self._on_primitive_bool_changed
        self.primitive_bool_inputs[key] = checkbox
        row.add_child(checkbox)
        body.add_child(row)

    def _build_plane_vector_row(self, group: str, axis: str) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)
        label = Label()
        label.text = axis.upper()
        label.color = (0.58, 0.64, 0.72, 1.0)
        label.preferred_width = px(18)
        row.add_child(label)
        spin = SpinBox()
        spin.decimals = 3
        spin.step = 0.1
        spin.min_value = -1000000.0
        spin.max_value = 1000000.0
        spin.preferred_height = px(24)
        spin.stretch = True
        spin.on_changed = self._on_plane_param_changed
        self.plane_inputs[f"{group}.{axis}"] = spin
        row.add_child(spin)
        return row

    def _build_contour_point_row(self, point_index: int) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)
        label = Label()
        label.text = f"P{point_index}"
        label.color = (0.58, 0.64, 0.72, 1.0)
        label.preferred_width = px(32)
        row.add_child(label)
        for axis in ("x", "y"):
            axis_label = Label()
            axis_label.text = axis.upper()
            axis_label.color = (0.58, 0.64, 0.72, 1.0)
            axis_label.preferred_width = px(14)
            row.add_child(axis_label)
            spin = SpinBox()
            spin.decimals = 3
            spin.step = 0.1
            spin.min_value = -1000000.0
            spin.max_value = 1000000.0
            spin.preferred_height = px(24)
            spin.stretch = True
            spin.on_changed = lambda value, i=point_index, a=axis: self._on_contour_point_changed(i, a, value)
            self.contour_point_inputs[(point_index, axis)] = spin
            row.add_child(spin)
        return row

    def _on_wireframe_changed(self, checked: bool) -> None:
        if self._wireframe_setter is not None:
            self._wireframe_setter(bool(checked))

    def _on_extrude_vector_changed(self, _value: float) -> None:
        if self._syncing_operation_params:
            return
        operation = self._selected_operation()
        if operation is None:
            log.error(f"{self._log_prefix} cannot update extrude vector: no operation is selected")
            return
        vector = (
            float(self.extrude_vector_inputs["x"].value),
            float(self.extrude_vector_inputs["y"].value),
            float(self.extrude_vector_inputs["z"].value),
        )
        result = self.controller.set_extrude_vector(operation.id, vector)
        if not self._dispatch_result(result):
            return
        log.info(
            f"{self._log_prefix} extrude vector changed "
            f"operation='{operation.id}' vector=({vector[0]:.3f}, {vector[1]:.3f}, {vector[2]:.3f})"
        )

    def _on_wall_param_changed(self, _value: float) -> None:
        if self._syncing_operation_params:
            return
        self._apply_wall_params_from_inputs()

    def _apply_wall_params_from_inputs(self, alignment: str | None = None) -> None:
        operation = self._selected_operation()
        if operation is None:
            log.error(f"{self._log_prefix} cannot update wall params: no operation is selected")
            return
        if operation.kind != OPERATION_KIND_WALL:
            log.error(
                f"{self._log_prefix} cannot update wall params: "
                f"operation '{operation.id}' has kind '{operation.kind}'"
            )
            return
        if "height" not in self.wall_param_inputs or "thickness" not in self.wall_param_inputs:
            log.error(f"{self._log_prefix} cannot update wall params: input widgets are missing operation='{operation.id}'")
            return
        next_alignment = str(alignment if alignment is not None else operation.params.get("alignment", "center"))
        height = float(self.wall_param_inputs["height"].value)
        thickness = float(self.wall_param_inputs["thickness"].value)
        result = self.controller.set_wall_params(operation.id, height, thickness, next_alignment)
        if not self._dispatch_result(result):
            return
        self.wall_alignment_label.text = f"Alignment: {next_alignment}"
        log.info(
            f"{self._log_prefix} wall params changed "
            f"operation='{operation.id}' height={height:.3f} thickness={thickness:.3f} alignment='{next_alignment}'"
        )

    def _on_operation_transform_changed(self, _value: float) -> None:
        if self._syncing_operation_params:
            return
        operation = self._selected_operation()
        if operation is None:
            log.error(f"{self._log_prefix} cannot update operation transform: no operation is selected")
            return
        center = self._operation_transform_vec("center")
        rotation = self._operation_transform_vec("rotation")
        result = self.controller.set_operation_transform(operation.id, center, rotation)
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} operation transform changed operation='{operation.id}' center={center} rotation={rotation}")

    def _on_primitive_param_changed(self, _value: float) -> None:
        if self._syncing_primitive_params:
            return
        self._apply_primitive_params_from_inputs()

    def _on_primitive_bool_changed(self, _checked: bool) -> None:
        if self._syncing_primitive_params:
            return
        self._apply_primitive_params_from_inputs()

    def _apply_primitive_params_from_inputs(self) -> None:
        operation = self._selected_primitive_operation()
        if operation is None:
            log.error(f"{self._log_prefix} cannot update primitive params: no primitive operation is selected")
            return
        primitive_kind = str(operation.params.get("primitive_kind", ""))
        spec = primitive_spec(primitive_kind)
        if spec is None:
            log.error(f"{self._log_prefix} cannot update primitive params: unknown primitive kind '{primitive_kind}'")
            return
        integer_param_keys = {param.key for param in spec.param_schema if param.kind == "int"}
        params: dict = {}
        vector_groups: dict[str, dict[str, float]] = {}
        for key, spin in self.primitive_param_inputs.items():
            if "." in key:
                group, axis = key.split(".", 1)
                vector_group = vector_groups.get(group)
                if vector_group is None:
                    vector_group = {}
                    vector_groups[group] = vector_group
                vector_group[axis] = float(spin.value)
                continue
            value = float(spin.value)
            if key in integer_param_keys:
                params[key] = int(round(value))
            else:
                params[key] = value
        for group, values in vector_groups.items():
            if "x" in values and "y" in values and "z" in values:
                params[group] = [values["x"], values["y"], values["z"]]
        for key, checkbox in self.primitive_bool_inputs.items():
            params[key] = bool(checkbox.checked)
        result = self.controller.set_primitive_params(operation.id, params)
        if not self._dispatch_result(result):
            return
        log.info(f"{self._log_prefix} primitive params changed operation='{operation.id}' params={params}")

    def _on_plane_param_changed(self, _value: float) -> None:
        if self._syncing_plane_params:
            return
        sketch = self._selected_plane_sketch()
        if sketch is None:
            log.error(f"{self._log_prefix} cannot update plane: no plane is selected")
            return
        plane = ProceduralPlane(
            origin=self._plane_input_vec("origin"),
            x_axis=self._plane_input_vec("x_axis"),
            y_axis=self._plane_input_vec("y_axis"),
        )
        result = self.controller.set_sketch_plane(sketch.id, plane)
        if not self._dispatch_result(result):
            return
        log.info(
            f"{self._log_prefix} plane changed "
            f"sketch='{sketch.id}' origin={plane.origin} x_axis={plane.x_axis} y_axis={plane.y_axis}"
        )

    def _on_contour_point_changed(self, point_index: int, axis: str, _value: float) -> None:
        if self._syncing_contour_params:
            return
        contour_ref = self._selected_contour_ref()
        if contour_ref is None:
            log.error(f"{self._log_prefix} cannot update contour point: no contour is selected")
            return
        _sketch, contour = contour_ref
        x_key = (point_index, "x")
        y_key = (point_index, "y")
        if x_key not in self.contour_point_inputs or y_key not in self.contour_point_inputs:
            log.error(
                f"{self._log_prefix} cannot update contour point: "
                f"input widgets are missing contour='{contour.id}' index={point_index} axis='{axis}'"
            )
            return
        point = (
            float(self.contour_point_inputs[x_key].value),
            float(self.contour_point_inputs[y_key].value),
        )
        result = self.controller.set_contour_point(contour.id, point_index, point)
        if not self._dispatch_result(result):
            return
        log.info(
            f"{self._log_prefix} contour point changed "
            f"contour='{contour.id}' index={point_index} point=({point[0]:.3f}, {point[1]:.3f})"
        )

    def _operation_transform_vec(self, group: str) -> tuple[float, float, float]:
        return (
            float(self.operation_transform_inputs[f"{group}.x"].value),
            float(self.operation_transform_inputs[f"{group}.y"].value),
            float(self.operation_transform_inputs[f"{group}.z"].value),
        )

    def _set_plane_input_vec(self, group: str, value: tuple[float, float, float]) -> None:
        self.plane_inputs[f"{group}.x"].value = value[0]
        self.plane_inputs[f"{group}.y"].value = value[1]
        self.plane_inputs[f"{group}.z"].value = value[2]

    def _plane_input_vec(self, group: str) -> tuple[float, float, float]:
        return (
            float(self.plane_inputs[f"{group}.x"].value),
            float(self.plane_inputs[f"{group}.y"].value),
            float(self.plane_inputs[f"{group}.z"].value),
        )

    def _set_operation_params_visible(self, visible: bool) -> None:
        self._set_visible(self.operation_params_panel, visible)

    def _set_primitive_params_visible(self, visible: bool) -> None:
        self._set_visible(self.primitive_params_panel, visible)

    def _set_plane_params_visible(self, visible: bool) -> None:
        self._set_visible(self.plane_params_panel, visible)

    def _set_contour_params_visible(self, visible: bool) -> None:
        self._set_visible(self.contour_params_panel, visible)

    def _set_context_actions_visible(self, visible: bool) -> None:
        self._set_visible(self.context_actions_panel, visible)

    def _set_visible(self, panel: Panel, visible: bool) -> None:
        if panel.visible == visible:
            return
        panel.visible = visible
        self._request_layout()

    def _request_layout(self) -> None:
        if self._request_layout_callback is not None:
            self._request_layout_callback()
            return
        if self.operation_params_panel._ui is not None:
            self.operation_params_panel._ui.request_layout()

    def _clear_children(self, panel: Panel) -> None:
        for child in panel.children[:]:
            panel.remove_child(child)

    def _mode_text(self) -> str:
        return f"Mode: {self.controller.mode}; draft points: {len(self.controller.draft.points)}"


def _contour_role_label(role: str) -> str:
    if role == CONTOUR_ROLE_HOLE:
        return "Hole"
    return "Outer"


def _param_vec3(params: dict, key: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    value = params.get(key, default)
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return default


def _param_float(params: dict, key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except Exception:
        return default


__all__ = ["CsgEditorPanel"]
