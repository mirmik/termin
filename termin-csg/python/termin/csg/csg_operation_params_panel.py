"""Operation parameter panel for the shared CSG editor UI."""

from __future__ import annotations

from typing import Callable

from tcbase import log
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.panel import Panel
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack

from termin.csg.csg_editor_panel_common import (
    COLOR_GROUP,
    COLOR_MUTED,
    COLOR_TITLE,
    clear_children,
    make_button,
    make_label,
    make_number_row,
    make_separator,
    param_float,
    param_vec3,
    set_visible,
    style_param_panel,
)
from termin.csg.document_eval import extrude_vector_for_operation
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController
from termin.csg.operation_specs import BOOLEAN_OPERATION_KINDS, PRIMITIVE_OPERATION_KIND
from termin.csg.procedural_document import OPERATION_KIND_WALL
from termin.csg.wall_height_offsets import MIN_WALL_CORNER_HEIGHT, wall_corner_height_offsets


DispatchResult = Callable[[CsgEditorCommandResult, str], bool]


class CsgOperationParamsPanel:
    def __init__(
        self,
        controller: CsgEditorController,
        dispatch_result: DispatchResult,
        request_layout: Callable[[], None],
        *,
        log_prefix: str,
    ) -> None:
        self.controller = controller
        self._dispatch_result = dispatch_result
        self._request_layout = request_layout
        self._log_prefix = log_prefix

        self.panel = Panel()
        self.title = Label()
        self.kind_label = Label()
        self.extrude_vector_inputs: dict[str, SpinBox] = {}
        self.wall_param_inputs: dict[str, SpinBox] = {}
        self.wall_offset_inputs: dict[tuple[str, int], SpinBox] = {}
        self.wall_alignment_label = Label()
        self.transform_inputs: dict[str, SpinBox] = {}
        self._syncing = False

    @property
    def document(self):
        return self.controller.document

    @property
    def selection(self) -> tuple[str, str] | None:
        return self.controller.selection

    def build(self) -> Panel:
        clear_children(self.panel)
        self.extrude_vector_inputs.clear()
        self.wall_param_inputs.clear()
        self.wall_offset_inputs.clear()
        self.transform_inputs.clear()
        style_param_panel(self.panel)
        return self.panel

    def refresh(self) -> None:
        operation = self._selected_operation()
        if operation is None:
            self._set_visible(False)
            return
        if operation.kind == PRIMITIVE_OPERATION_KIND:
            self._set_visible(False)
            return
        if operation.kind not in {"extrude", OPERATION_KIND_WALL} and operation.kind not in BOOLEAN_OPERATION_KINDS:
            self._set_visible(False)
            return
        if not self._rebuild(operation):
            self._set_visible(False)
            return
        self._set_visible(True)

    def set_wall_alignment(self, alignment: str) -> None:
        if self._syncing:
            return
        self._apply_wall_params_from_inputs(alignment=alignment)

    def _rebuild(self, operation) -> bool:
        clear_children(self.panel)
        self.extrude_vector_inputs.clear()
        self.wall_param_inputs.clear()
        self.wall_offset_inputs.clear()
        self.transform_inputs.clear()

        body = VStack()
        body.spacing = 5

        self.title.text = operation.name
        self.title.color = COLOR_TITLE
        body.add_child(self.title)
        self.kind_label.text = f"Kind: {operation.kind}"
        self.kind_label.color = COLOR_MUTED
        body.add_child(self.kind_label)
        body.add_child(make_separator())

        self._syncing = True
        if operation.kind == "extrude":
            if not self._append_extrude_rows(body, operation):
                self._syncing = False
                return False
        if operation.kind == OPERATION_KIND_WALL:
            if not self._append_wall_rows(body, operation):
                self._syncing = False
                return False

        self._append_transform_rows(body, "center", "Center", operation.params)
        self._append_transform_rows(body, "rotation", "Rotation", operation.params)
        self._syncing = False
        self.panel.add_child(body)
        return True

    def _append_extrude_rows(self, body: VStack, operation) -> bool:
        source_sketch_id = str(operation.params.get("source_sketch_id", ""))
        sketch = self.document.find_sketch(source_sketch_id)
        if sketch is None:
            log.error(
                f"{self._log_prefix} cannot show extrude parameters: "
                f"source sketch not found '{source_sketch_id}'"
            )
            return False
        vector = extrude_vector_for_operation(sketch, operation)
        body.add_child(make_label("Extrude vector", COLOR_GROUP))
        for axis in ("x", "y", "z"):
            row = self._build_vector_row(axis)
            self.extrude_vector_inputs[axis].value = vector[("x", "y", "z").index(axis)]
            body.add_child(row)
        return True

    def _append_wall_rows(self, body: VStack, operation) -> bool:
        source_sketch_id = str(operation.params.get("source_sketch_id", ""))
        sketch = self.document.find_sketch(source_sketch_id)
        if sketch is None:
            log.error(
                f"{self._log_prefix} cannot show wall parameters: "
                f"source sketch not found '{source_sketch_id}'"
            )
            return False
        body.add_child(make_label("Wall", COLOR_GROUP))
        body.add_child(
            self._build_wall_number_row(
                "height",
                "Height",
                param_float(operation.params, "height", 3.0),
                min_value=0.001,
            )
        )
        body.add_child(
            self._build_wall_number_row(
                "thickness",
                "Thickness",
                param_float(operation.params, "thickness", 0.2),
                min_value=0.001,
            )
        )
        self.wall_alignment_label.text = f"Alignment: {operation.params.get('alignment', 'center')}"
        self.wall_alignment_label.color = COLOR_MUTED
        body.add_child(self.wall_alignment_label)
        alignment_row = HStack()
        alignment_row.spacing = 4
        alignment_row.preferred_height = px(28)
        alignment_row.add_child(make_button("Center", lambda: self.set_wall_alignment("center")))
        alignment_row.add_child(make_button("Left", lambda: self.set_wall_alignment("left")))
        alignment_row.add_child(make_button("Right", lambda: self.set_wall_alignment("right")))
        body.add_child(alignment_row)
        self._append_wall_corner_offset_rows(body, operation, sketch)
        return True

    def _build_vector_row(self, axis: str) -> HStack:
        row, spin = make_number_row(
            axis.upper(),
            0.0,
            self._on_extrude_vector_changed,
            label_width=18,
        )
        self.extrude_vector_inputs[axis] = spin
        return row

    def _build_wall_number_row(
        self,
        key: str,
        label_text: str,
        value: float,
        min_value: float = -1000000.0,
    ) -> HStack:
        row, spin = make_number_row(
            label_text,
            value,
            self._on_wall_param_changed,
            min_value=min_value,
        )
        self.wall_param_inputs[key] = spin
        return row

    def _append_wall_corner_offset_rows(self, body: VStack, operation, sketch) -> None:
        base_height = param_float(operation.params, "height", 3.0)
        min_offset = MIN_WALL_CORNER_HEIGHT - base_height
        input_ids = set(operation.inputs)
        body.add_child(make_label("Corner offsets", COLOR_GROUP))
        for path in sketch.paths:
            if path.id not in input_ids:
                continue
            self._append_wall_source_offset_rows(body, operation, path.id, "Path", len(path.points), min_offset)
        for contour in sketch.outer_contours():
            if contour.id not in input_ids:
                continue
            if sketch.hole_contours_for_outer(contour.id):
                continue
            self._append_wall_source_offset_rows(body, operation, contour.id, "Contour", len(contour.points), min_offset)

    def _append_wall_source_offset_rows(
        self,
        body: VStack,
        operation,
        source_id: str,
        source_label: str,
        point_count: int,
        min_offset: float,
    ) -> None:
        offsets = wall_corner_height_offsets(
            operation.params,
            source_id,
            point_count,
            operation_id=operation.id,
        )
        for index, offset in enumerate(offsets):
            row, spin = make_number_row(
                f"{source_label} P{index}",
                offset,
                lambda value, s=source_id, i=index: self._on_wall_corner_offset_changed(s, i, value),
                min_value=min_offset,
            )
            self.wall_offset_inputs[(source_id, index)] = spin
            body.add_child(row)

    def _append_transform_rows(self, body: VStack, group: str, label_text: str, params: dict) -> None:
        body.add_child(make_label(label_text, COLOR_GROUP))
        value = param_vec3(params, group, (0.0, 0.0, 0.0))
        for index, axis in enumerate(("x", "y", "z")):
            key = f"{group}.{axis}"
            row, spin = make_number_row(
                axis.upper(),
                value[index],
                self._on_operation_transform_changed,
                label_width=18,
            )
            self.transform_inputs[key] = spin
            body.add_child(row)

    def _on_extrude_vector_changed(self, _value: float) -> None:
        if self._syncing:
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
        if not self._dispatch_result(result, ""):
            return
        log.info(
            f"{self._log_prefix} extrude vector changed "
            f"operation='{operation.id}' vector=({vector[0]:.3f}, {vector[1]:.3f}, {vector[2]:.3f})"
        )

    def _on_wall_param_changed(self, _value: float) -> None:
        if self._syncing:
            return
        self._apply_wall_params_from_inputs()

    def _on_wall_corner_offset_changed(self, source_id: str, point_index: int, value: float) -> None:
        if self._syncing:
            return
        operation = self._selected_operation()
        if operation is None:
            log.error(f"{self._log_prefix} cannot update wall corner offset: no operation is selected")
            return
        result = self.controller.set_wall_corner_offset(operation.id, source_id, point_index, float(value))
        if not self._dispatch_result(result, ""):
            return
        log.info(
            f"{self._log_prefix} wall corner offset changed "
            f"operation='{operation.id}' source='{source_id}' index={point_index} offset={float(value):.3f}"
        )

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
        if not self._dispatch_result(result, ""):
            return
        self.wall_alignment_label.text = f"Alignment: {next_alignment}"
        log.info(
            f"{self._log_prefix} wall params changed "
            f"operation='{operation.id}' height={height:.3f} thickness={thickness:.3f} alignment='{next_alignment}'"
        )

    def sync_wall_corner_offset_input(self, source_id: str, point_index: int, offset: float) -> None:
        spin = self.wall_offset_inputs.get((source_id, int(point_index)))
        if spin is None:
            return
        self._syncing = True
        spin.value = float(offset)
        self._syncing = False

    def _on_operation_transform_changed(self, _value: float) -> None:
        if self._syncing:
            return
        operation = self._selected_operation()
        if operation is None:
            log.error(f"{self._log_prefix} cannot update operation transform: no operation is selected")
            return
        center = self._transform_vec("center")
        rotation = self._transform_vec("rotation")
        result = self.controller.set_operation_transform(operation.id, center, rotation)
        if not self._dispatch_result(result, ""):
            return
        log.info(f"{self._log_prefix} operation transform changed operation='{operation.id}' center={center} rotation={rotation}")

    def _transform_vec(self, group: str) -> tuple[float, float, float]:
        return (
            float(self.transform_inputs[f"{group}.x"].value),
            float(self.transform_inputs[f"{group}.y"].value),
            float(self.transform_inputs[f"{group}.z"].value),
        )

    def _selected_operation(self):
        if self.selection is None:
            return None
        kind, item_id = self.selection
        if kind != "operation":
            return None
        return self.document.find_operation(item_id)

    def _set_visible(self, visible: bool) -> None:
        set_visible(self.panel, visible, self._request_layout)


__all__ = ["CsgOperationParamsPanel"]
