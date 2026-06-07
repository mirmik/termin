"""Primitive operation parameter panel for the shared CSG editor UI."""

from __future__ import annotations

from typing import Callable

from tcbase import log
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.panel import Panel
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack

from termin.csg.csg_editor_panel_common import (
    COLOR_GROUP,
    COLOR_TITLE,
    clear_children,
    make_number_row,
    make_separator,
    param_vec3,
    set_visible,
    style_param_panel,
)
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController
from termin.csg.operation_specs import OperationParamSpec, PRIMITIVE_OPERATION_KIND, primitive_label, primitive_spec


DispatchResult = Callable[[CsgEditorCommandResult, str], bool]


class CsgPrimitiveParamsPanel:
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
        self.param_inputs: dict[str, SpinBox] = {}
        self.bool_inputs: dict[str, Checkbox] = {}
        self._syncing = False

    @property
    def document(self):
        return self.controller.document

    @property
    def selection(self) -> tuple[str, str] | None:
        return self.controller.selection

    def build(self) -> Panel:
        clear_children(self.panel)
        self.param_inputs.clear()
        self.bool_inputs.clear()
        style_param_panel(self.panel)
        return self.panel

    def refresh(self) -> None:
        operation = self._selected_primitive_operation()
        if operation is None:
            self._set_visible(False)
            return
        self._rebuild(operation)
        self._set_visible(True)

    def _rebuild(self, operation) -> None:
        clear_children(self.panel)
        self.param_inputs.clear()
        self.bool_inputs.clear()
        body = VStack()
        body.spacing = 5

        primitive_kind = str(operation.params.get("primitive_kind", ""))
        spec = primitive_spec(primitive_kind)
        self.title.text = f"{primitive_label(primitive_kind)}: {operation.name}"
        self.title.color = COLOR_TITLE
        body.add_child(self.title)
        body.add_child(make_separator())

        self._syncing = True
        if spec is None:
            log.error(f"{self._log_prefix} cannot build primitive params: unknown primitive kind '{primitive_kind}'")
        else:
            self._append_schema_rows(body, spec.param_schema, operation.params)
        self._syncing = False
        self.panel.add_child(body)

    def _append_schema_rows(
        self,
        body: VStack,
        param_schema: tuple[OperationParamSpec, ...],
        params: dict,
    ) -> None:
        for param in param_schema:
            if param.kind == "vec3":
                default_vec = param_vec3({"value": param.default}, "value", (0.0, 0.0, 0.0))
                min_value = -1000000.0 if param.min_value is None else float(param.min_value)
                self._append_vector_rows(
                    body,
                    param.key,
                    param.label,
                    params,
                    default_vec,
                    min_value=min_value,
                )
            elif param.kind == "bool":
                self._append_bool_row(body, param.key, param.label, params, bool(param.default))
            elif param.kind == "int":
                body.add_child(
                    self._build_number_row(
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
                    self._build_number_row(
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

    def _append_vector_rows(
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
        label.color = COLOR_GROUP
        body.add_child(label)
        value = param_vec3(params, group, default)
        for index, axis in enumerate(("x", "y", "z")):
            key = f"{group}.{axis}"
            row = self._build_number_row(
                key,
                axis.upper(),
                {},
                value[index],
                min_value=min_value,
                label_width=18,
            )
            body.add_child(row)

    def _build_number_row(
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
        row, spin = make_number_row(
            label_text,
            float(params.get(key, default)),
            self._on_param_changed,
            decimals=decimals,
            step=step,
            min_value=min_value,
            max_value=max_value,
            label_width=label_width,
        )
        self.param_inputs[key] = spin
        return row

    def _append_bool_row(self, body: VStack, key: str, label_text: str, params: dict, default: bool) -> None:
        row = HStack()
        row.spacing = 4
        row.preferred_height = px(24)
        checkbox = Checkbox()
        checkbox.text = label_text
        checkbox.checked = bool(params.get(key, default))
        checkbox.on_changed = self._on_bool_changed
        self.bool_inputs[key] = checkbox
        row.add_child(checkbox)
        body.add_child(row)

    def _on_param_changed(self, _value: float) -> None:
        if self._syncing:
            return
        self._apply_params_from_inputs()

    def _on_bool_changed(self, _checked: bool) -> None:
        if self._syncing:
            return
        self._apply_params_from_inputs()

    def _apply_params_from_inputs(self) -> None:
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
        for key, spin in self.param_inputs.items():
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
        for key, checkbox in self.bool_inputs.items():
            params[key] = bool(checkbox.checked)
        result = self.controller.set_primitive_params(operation.id, params)
        if not self._dispatch_result(result, ""):
            return
        log.info(f"{self._log_prefix} primitive params changed operation='{operation.id}' params={params}")

    def _selected_primitive_operation(self):
        if self.selection is None:
            return None
        kind, item_id = self.selection
        if kind != "operation":
            return None
        operation = self.document.find_operation(item_id)
        if operation is None or operation.kind != PRIMITIVE_OPERATION_KIND:
            return None
        return operation

    def _set_visible(self, visible: bool) -> None:
        set_visible(self.panel, visible, self._request_layout)


__all__ = ["CsgPrimitiveParamsPanel"]
