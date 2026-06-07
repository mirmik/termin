"""Sketch-related parameter panels for the shared CSG editor UI."""

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
    make_label,
    make_number_row,
    make_separator,
    make_spin_box,
    set_visible,
    style_param_panel,
)
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController
from termin.csg.procedural_document import CONTOUR_ROLE_HOLE, ProceduralPlane


DispatchResult = Callable[[CsgEditorCommandResult, str], bool]


class CsgPlaneParamsPanel:
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
        self.inputs: dict[str, SpinBox] = {}
        self._syncing = False

    @property
    def document(self):
        return self.controller.document

    @property
    def selection(self) -> tuple[str, str] | None:
        return self.controller.selection

    def build(self) -> Panel:
        clear_children(self.panel)
        self.inputs.clear()
        style_param_panel(self.panel)

        body = VStack()
        body.spacing = 5
        self.title.text = "Plane"
        self.title.color = COLOR_TITLE
        body.add_child(self.title)
        body.add_child(make_separator())
        for group, label_text in (
            ("origin", "Origin"),
            ("x_axis", "X axis"),
            ("y_axis", "Y axis"),
        ):
            body.add_child(make_label(label_text, COLOR_GROUP))
            for axis in ("x", "y", "z"):
                body.add_child(self._build_vector_row(group, axis))
        self.panel.add_child(body)
        return self.panel

    def refresh(self) -> None:
        sketch = self._selected_plane_sketch()
        if sketch is None:
            self._set_visible(False)
            return
        self.title.text = f"Plane: {sketch.name}"
        self._syncing = True
        self._set_input_vec("origin", sketch.plane.origin)
        self._set_input_vec("x_axis", sketch.plane.x_axis)
        self._set_input_vec("y_axis", sketch.plane.y_axis)
        self._syncing = False
        self._set_visible(True)

    def _build_vector_row(self, group: str, axis: str) -> HStack:
        row, spin = make_number_row(
            axis.upper(),
            0.0,
            self._on_param_changed,
            label_width=18,
        )
        self.inputs[f"{group}.{axis}"] = spin
        return row

    def _on_param_changed(self, _value: float) -> None:
        if self._syncing:
            return
        sketch = self._selected_plane_sketch()
        if sketch is None:
            log.error(f"{self._log_prefix} cannot update plane: no plane is selected")
            return
        plane = ProceduralPlane(
            origin=self._input_vec("origin"),
            x_axis=self._input_vec("x_axis"),
            y_axis=self._input_vec("y_axis"),
        )
        result = self.controller.set_sketch_plane(sketch.id, plane)
        if not self._dispatch_result(result, ""):
            return
        log.info(
            f"{self._log_prefix} plane changed "
            f"sketch='{sketch.id}' origin={plane.origin} x_axis={plane.x_axis} y_axis={plane.y_axis}"
        )

    def _set_input_vec(self, group: str, value: tuple[float, float, float]) -> None:
        self.inputs[f"{group}.x"].value = value[0]
        self.inputs[f"{group}.y"].value = value[1]
        self.inputs[f"{group}.z"].value = value[2]

    def _input_vec(self, group: str) -> tuple[float, float, float]:
        return (
            float(self.inputs[f"{group}.x"].value),
            float(self.inputs[f"{group}.y"].value),
            float(self.inputs[f"{group}.z"].value),
        )

    def _selected_plane_sketch(self):
        if self.selection is None:
            return None
        kind, item_id = self.selection
        if kind != "plane":
            return None
        return self.document.find_sketch(item_id)

    def _set_visible(self, visible: bool) -> None:
        set_visible(self.panel, visible, self._request_layout)


class CsgContourParamsPanel:
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
        self.point_inputs: dict[tuple[int, str], SpinBox] = {}
        self._syncing = False

    @property
    def document(self):
        return self.controller.document

    @property
    def selection(self) -> tuple[str, str] | None:
        return self.controller.selection

    def build(self) -> Panel:
        clear_children(self.panel)
        self.point_inputs.clear()
        style_param_panel(self.panel)
        return self.panel

    def refresh(self) -> None:
        contour_ref = self._selected_contour_ref()
        if contour_ref is None:
            self._set_visible(False)
            return
        _sketch, contour = contour_ref
        self._rebuild(contour)
        self._set_visible(True)

    def sync_point_inputs(self, point_index: int, point: tuple[float, float]) -> None:
        x_key = (point_index, "x")
        y_key = (point_index, "y")
        if x_key not in self.point_inputs or y_key not in self.point_inputs:
            return
        self._syncing = True
        try:
            self.point_inputs[x_key].value = point[0]
            self.point_inputs[y_key].value = point[1]
        finally:
            self._syncing = False

    def _rebuild(self, contour) -> None:
        clear_children(self.panel)
        self.point_inputs.clear()
        body = VStack()
        body.spacing = 5

        body.add_child(make_label(f"{_contour_role_label(contour.role)}: {contour.name}", COLOR_TITLE))
        body.add_child(make_label(self._contour_role_text(contour), COLOR_MUTED))
        body.add_child(make_label("Local points", COLOR_MUTED))
        body.add_child(make_separator())

        self._syncing = True
        for index, point in enumerate(contour.points):
            row = self._build_point_row(index)
            self.point_inputs[(index, "x")].value = point[0]
            self.point_inputs[(index, "y")].value = point[1]
            body.add_child(row)
        self._syncing = False
        self.panel.add_child(body)

    def _build_point_row(self, point_index: int) -> HStack:
        row = HStack()
        row.spacing = 6
        row.preferred_height = px(26)
        row.add_child(make_label(f"P{point_index}", width=32))
        for axis in ("x", "y"):
            row.add_child(make_label(axis.upper(), width=14))
            spin = make_spin_box(
                0.0,
                lambda value, i=point_index, a=axis: self._on_point_changed(i, a, value),
            )
            self.point_inputs[(point_index, axis)] = spin
            row.add_child(spin)
        return row

    def _on_point_changed(self, point_index: int, axis: str, _value: float) -> None:
        if self._syncing:
            return
        contour_ref = self._selected_contour_ref()
        if contour_ref is None:
            log.error(f"{self._log_prefix} cannot update contour point: no contour is selected")
            return
        _sketch, contour = contour_ref
        x_key = (point_index, "x")
        y_key = (point_index, "y")
        if x_key not in self.point_inputs or y_key not in self.point_inputs:
            log.error(
                f"{self._log_prefix} cannot update contour point: "
                f"input widgets are missing contour='{contour.id}' index={point_index} axis='{axis}'"
            )
            return
        point = (
            float(self.point_inputs[x_key].value),
            float(self.point_inputs[y_key].value),
        )
        result = self.controller.set_contour_point(contour.id, point_index, point)
        if not self._dispatch_result(result, ""):
            return
        log.info(
            f"{self._log_prefix} contour point changed "
            f"contour='{contour.id}' index={point_index} point=({point[0]:.3f}, {point[1]:.3f})"
        )

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

    def _set_visible(self, visible: bool) -> None:
        set_visible(self.panel, visible, self._request_layout)


def _contour_role_label(role: str) -> str:
    if role == CONTOUR_ROLE_HOLE:
        return "Hole"
    return "Outer"


__all__ = ["CsgContourParamsPanel", "CsgPlaneParamsPanel"]
