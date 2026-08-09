"""Reusable termin-gui-native projection for procedural CSG editing."""

from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
import logging

from termin.gui_native import (
    CollectionItem,
    CommandData,
    CommandModel,
    EdgeInsets,
    Point,
    Rect,
    Size,
    TcDocument,
    TreeDropPosition,
    TreeExpansionModel,
    TreeModel,
)

from termin.csg.document_tree_model import DocumentTreeNode, build_document_tree
from termin.csg.operation_specs import (
    BOOLEAN_OPERATION_KINDS,
    OPERATION_KIND_EXTRUDE,
    OPERATION_KIND_WALL,
    PRIMITIVE_OPERATION_KIND,
    ordered_boolean_operation_specs,
    ordered_primitive_specs,
    primitive_label,
    primitive_spec,
)
from termin.csg.procedural_document import CONTOUR_ROLE_OUTER, ProceduralPlane
from termin.csg.wall_height_offsets import MIN_WALL_CORNER_HEIGHT, wall_corner_height_offsets


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NativeCsgPanelMetrics:
    embedded_panel_insets: object = EdgeInsets(8.0, 8.0, 8.0, 8.0)
    spacing: float = 6.0
    dense_spacing: float = 4.0
    compact_spacing: float = 4.0
    section_row: float = 28.0
    compact_status_row: float = 22.0
    compact_row: float = 28.0


DEFAULT_NATIVE_CSG_PANEL_METRICS = NativeCsgPanelMetrics()


@dataclass
class NativeCsgEditorPanel:
    document: TcDocument
    model: object
    root: object | None
    tree_root: object
    inspector_root: object
    tree: object
    tree_model: TreeModel
    tree_expansion: TreeExpansionModel
    mode_label: object
    summary_label: object
    selection_label: object
    status_label: object
    action_host: object
    param_host: object
    context_model: CommandModel
    context_menu: object
    viewport: Callable[[], Rect]
    metrics: NativeCsgPanelMetrics

    def __post_init__(self) -> None:
        self._tree_selections: dict[int, tuple[str, str]] = {}
        self._tree_nodes: dict[int, DocumentTreeNode] = {}
        self._tree_keys: dict[int, str] = {}
        self._collapsed_keys: set[str] = set()
        self._applying_snapshot = False
        self._context_selection: tuple[str, str] | None = None

    def refresh(self) -> None:
        self.apply_snapshot(self.model.snapshot)

    def sync_contour_point_inputs(
        self,
        _point_index: int,
        _point: tuple[float, float],
    ) -> None:
        """Refresh selected point controls after a viewport drag mutation."""

        self._rebuild_params(self.model.controller.selection)

    def sync_wall_corner_offset_input(
        self,
        _source_id: str,
        _point_index: int,
        _offset: float,
    ) -> None:
        """Refresh selected wall controls after a viewport drag mutation."""

        self._rebuild_params(self.model.controller.selection)

    def close(self) -> None:
        self.model.set_changed_handler(None)
        if self.document.is_alive(self.context_menu.handle):
            self.context_menu.dismiss()
        handles = [self.context_menu.handle]
        if self.root is not None:
            handles.append(self.root.handle)
        else:
            handles.extend((self.tree_root.handle, self.inspector_root.handle))
        for handle in handles:
            if self.document.is_alive(handle):
                self.document.destroy_widget_recursive(handle)

    def apply_snapshot(self, snapshot) -> None:
        self.mode_label.text = f"Mode: {snapshot.mode}; draft points: {snapshot.draft_point_count}"
        self.summary_label.text = snapshot.document_summary
        self.selection_label.text = (
            "Selection: <none>"
            if snapshot.selection is None
            else f"Selection: {snapshot.selection[0]} {snapshot.selection[1][:10]}"
        )
        self.status_label.text = f"Status: {snapshot.status}"
        for label in (self.mode_label, self.summary_label, self.selection_label, self.status_label):
            label.widget.name = label.text
        self._rebuild_tree(snapshot.selection)
        self._rebuild_actions(snapshot.selection)
        self._rebuild_params(snapshot.selection)

    def select_tree_node(self, node: int) -> None:
        if self._applying_snapshot:
            return
        selection = self._tree_selections.get(node)
        if selection is not None:
            self.model.select_node(selection)

    def set_expanded(self, node: int, expanded: bool) -> None:
        if self._applying_snapshot:
            return
        key = self._tree_keys.get(node)
        if key is None:
            return
        if expanded:
            self._collapsed_keys.discard(key)
        else:
            self._collapsed_keys.add(key)

    def show_context_menu(self, node: int, x: float, y: float) -> None:
        selection = self._tree_selections.get(node)
        if selection is None:
            return
        self._context_selection = selection
        actions = self._context_actions(selection)
        if not actions:
            return
        self.context_model.set_commands([CommandData(action, label) for action, label in actions])
        if not self.context_menu.show(Point(x, y), self.viewport()):
            _logger.error("Native CSG tree failed to show context menu")

    def execute_context_action(self, action: str) -> None:
        selection = self._context_selection
        if selection is not None and selection != self.model.controller.selection:
            if not self.model.select_node(selection):
                return
        commands = {
            "add-outer": self.model.start_add_outer_contour,
            "add-hole": self.model.start_add_hole_contour,
            "add-wall-path": self.model.start_add_wall_path,
            "wall": self.model.wall_selected,
            "extrude": self.model.extrude_selected,
        }
        command = commands.get(action)
        if command is None:
            _logger.error("Native CSG received unknown context action '%s'", action)
            return
        command()

    def drop_node(self, dragged: int, target: int, position: TreeDropPosition) -> None:
        dragged_model = self._tree_nodes.get(dragged)
        target_model = self._tree_nodes.get(target)
        if dragged_model is None or dragged_model.kind != "operation":
            _logger.error("Native CSG tree drop requires an operation node")
            return
        operation_id = dragged_model.item_id
        controller = self.model.controller
        source_boolean_id = dragged_model.parent_operation_id if dragged_model.is_boolean_input else ""
        if position == TreeDropPosition.Root:
            if source_boolean_id:
                self.model.apply_result(controller.remove_boolean_input(source_boolean_id, operation_id))
            return
        if position == TreeDropPosition.Inside:
            if target_model is None or not target_model.accepts_drop_inside:
                _logger.error("Native CSG tree inside-drop target is not a boolean operation")
                return
            target_boolean_id = target_model.item_id
            if source_boolean_id == target_boolean_id:
                _logger.error("Native CSG tree input is already inside the target operation")
                return
            result = (
                controller.move_boolean_input(source_boolean_id, target_boolean_id, operation_id)
                if source_boolean_id
                else controller.add_boolean_input(target_boolean_id, operation_id)
            )
            self.model.apply_result(result)
            return
        if target_model is None or not target_model.accepts_drop_above_below:
            _logger.error("Native CSG tree before/after drop requires a boolean input target")
            return
        target_operation = controller.document.find_operation(target_model.parent_operation_id)
        if target_operation is None or not 0 <= target_model.input_index < len(target_operation.inputs):
            _logger.error("Native CSG tree drop target has invalid boolean input metadata")
            return
        insert_index = target_model.input_index
        if position == TreeDropPosition.After:
            insert_index += 1
        target_boolean_id = target_model.parent_operation_id
        result = (
            controller.move_boolean_input(
                source_boolean_id,
                target_boolean_id,
                operation_id,
                insert_index,
            )
            if source_boolean_id
            else controller.add_boolean_input(target_boolean_id, operation_id, insert_index)
        )
        self.model.apply_result(result)

    def _rebuild_tree(self, selection: tuple[str, str] | None) -> None:
        self._applying_snapshot = True
        try:
            self.tree_model.clear()
            self.tree_expansion.clear()
            self._tree_selections.clear()
            self._tree_nodes.clear()
            self._tree_keys.clear()
            selected_node = None

            def append(source: DocumentTreeNode, parent: int | None, path: str) -> None:
                nonlocal selected_node
                segment = f"{source.kind}:{source.item_id}"
                if source.input_index >= 0:
                    segment += f"@{source.input_index}"
                stable_key = f"{path}/{segment}"
                item = CollectionItem(stable_key, source.text, source.kind)
                if source.kind == "info":
                    item.enabled = False
                node = (
                    self.tree_model.append_root(item) if parent is None else self.tree_model.append_child(parent, item)
                )
                self._tree_nodes[node] = source
                self._tree_keys[node] = stable_key
                if source.kind != "info":
                    node_selection = (source.kind, source.item_id)
                    self._tree_selections[node] = node_selection
                    if selected_node is None and node_selection == selection:
                        selected_node = node
                if source.children and stable_key not in self._collapsed_keys:
                    self.tree_expansion.set_expanded(node, True)
                for child in source.children:
                    append(child, node, stable_key)

            for source in build_document_tree(self.model.controller.document):
                append(source, None, "document")
            if selected_node is None:
                self.tree.clear_selection()
            else:
                self.tree.select(selected_node, reveal=True)
        finally:
            self._applying_snapshot = False

    def _clear_host(self, host) -> None:
        for child in tuple(host.children):
            if not self.document.destroy_widget_recursive(child.handle):
                raise RuntimeError("failed to destroy native CSG editor row")

    def _context_actions(self, selection: tuple[str, str] | None) -> list[tuple[str, str]]:
        if selection is None:
            return []
        kind, item_id = selection
        csg_document = self.model.controller.document
        if kind == "sketch" and csg_document.find_sketch(item_id) is not None:
            return [
                ("add-outer", "Add Outer Contour"),
                ("add-wall-path", "Add Wall Path"),
                ("wall", "Wall"),
                ("extrude", "Extrude Sketch"),
            ]
        if kind == "contour":
            contour_ref = csg_document.find_contour_ref(item_id)
            if contour_ref is not None and contour_ref[1].role == CONTOUR_ROLE_OUTER:
                return [("add-hole", "Add Hole")]
        return []

    def _rebuild_actions(self, selection: tuple[str, str] | None) -> None:
        self._clear_host(self.action_host)
        actions = self._context_actions(selection)
        self.action_host.visible = bool(actions)
        if not actions:
            return
        self.action_host.add_fixed_child(
            self.document.create_label("Actions", "native-procedural-actions-title"),
            20.0,
        )
        for action, label in actions:
            button = self.document.create_button(label, f"native-procedural-action-{action}")
            button.connect_clicked(lambda command=action: self._execute_for_selection(command, selection))
            self.action_host.add_fixed_child(button.widget, self.metrics.compact_row)

    def _execute_for_selection(self, action: str, selection: tuple[str, str] | None) -> None:
        self._context_selection = selection
        self.execute_context_action(action)

    @staticmethod
    def _vector(params: dict, key: str, default) -> tuple[float, float, float]:
        value = params.get(key, default)
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (IndexError, TypeError, ValueError):
            return (float(default[0]), float(default[1]), float(default[2]))

    def _append_vector(self, key: str, label: str, values, changed) -> None:
        self.param_host.add_fixed_child(
            self.document.create_label(label, f"native-procedural-param-label-{key}"),
            20.0,
        )
        row = self.document.create_hstack(f"native-procedural-param-row-{key}")
        row.set_layout_spacing(self.metrics.compact_spacing)
        boxes = []
        for axis, value in zip(("x", "y", "z"), values, strict=True):
            box = self.document.create_spin_box(float(value))
            box.widget.debug_name = f"native-procedural-param-{key}-{axis}"
            box.set_range(-1.0e6, 1.0e6)
            box.step = 0.1
            box.decimals = 3
            boxes.append(box)
            row.add_stretch_child(box.widget)

        def vector_changed(_value: float) -> None:
            changed(tuple(float(box.value) for box in boxes))

        for box in boxes:
            box.connect_changed(vector_changed)
        self.param_host.add_fixed_child(row, self.metrics.compact_row)

    def _append_scalar(
        self,
        key: str,
        label: str,
        value: float,
        changed,
        *,
        min_value: float = 0.001,
        max_value: float = 1.0e6,
        integer: bool = False,
    ) -> None:
        row = self.document.create_hstack(f"native-procedural-param-row-{key}")
        row.set_layout_spacing(self.metrics.dense_spacing)
        row.add_fixed_child(
            self.document.create_label(label, f"native-procedural-param-label-{key}"),
            104.0,
        )
        box = self.document.create_spin_box(float(value))
        box.widget.debug_name = f"native-procedural-param-{key}"
        box.set_range(min_value, max_value)
        box.step = 1.0 if integer else 0.1
        box.decimals = 0 if integer else 3
        box.connect_changed(lambda updated: changed(int(round(updated)) if integer else float(updated)))
        row.add_stretch_child(box.widget)
        self.param_host.add_fixed_child(row, self.metrics.compact_row)

    def _append_title(self, text: str) -> None:
        self.param_host.visible = True
        self.param_host.add_fixed_child(
            self.document.create_label(text, "native-procedural-param-title"),
            22.0,
        )

    def _rebuild_params(self, selection: tuple[str, str] | None) -> None:
        self._clear_host(self.param_host)
        self.param_host.visible = False
        if selection is None:
            return
        kind, item_id = selection
        csg_document = self.model.controller.document
        if kind == "plane":
            sketch = csg_document.find_sketch(item_id)
            if sketch is not None:
                self._rebuild_plane(sketch)
            return
        if kind in ("contour", "path"):
            item_ref = (
                csg_document.find_contour_ref(item_id) if kind == "contour" else csg_document.find_path_ref(item_id)
            )
            if item_ref is not None:
                self._rebuild_points(kind, item_ref[1])
            return
        if kind != "operation":
            return
        operation = csg_document.find_operation(item_id)
        if operation is None:
            return
        if operation.kind == PRIMITIVE_OPERATION_KIND:
            self._rebuild_primitive(operation)
        elif operation.kind in {OPERATION_KIND_EXTRUDE, OPERATION_KIND_WALL, *BOOLEAN_OPERATION_KINDS}:
            self._rebuild_operation(operation)

    def _rebuild_plane(self, sketch) -> None:
        self._append_title(f"Plane: {sketch.name}")
        groups = {}
        for key, label, values in (
            ("origin", "Origin", sketch.plane.origin),
            ("x-axis", "X Axis", sketch.plane.x_axis),
            ("y-axis", "Y Axis", sketch.plane.y_axis),
        ):
            controls = []
            self.param_host.add_fixed_child(
                self.document.create_label(label, f"native-procedural-param-label-{key}"), 20.0
            )
            row = self.document.create_hstack(f"native-procedural-param-row-{key}")
            row.set_layout_spacing(self.metrics.compact_spacing)
            for axis, value in zip(("x", "y", "z"), values, strict=True):
                box = self.document.create_spin_box(float(value))
                box.widget.debug_name = f"native-procedural-param-{key}-{axis}"
                box.set_range(-1.0e6, 1.0e6)
                box.step = 0.1
                box.decimals = 3
                controls.append(box)
                row.add_stretch_child(box.widget)
            groups[key] = controls
            self.param_host.add_fixed_child(row, self.metrics.compact_row)

        def changed(_value: float) -> None:
            values = lambda key: tuple(float(box.value) for box in groups[key])
            self.model.set_sketch_plane(
                sketch.id,
                ProceduralPlane(
                    origin=values("origin"),
                    x_axis=values("x-axis"),
                    y_axis=values("y-axis"),
                ),
            )

        for controls in groups.values():
            for box in controls:
                box.connect_changed(changed)

    def _rebuild_points(self, kind: str, item) -> None:
        self._append_title(f"{'Contour' if kind == 'contour' else 'Path'}: {item.name}")
        for index, point in enumerate(item.points):
            row = self.document.create_hstack(f"native-procedural-param-row-point-{index}")
            row.set_layout_spacing(self.metrics.dense_spacing)
            row.add_fixed_child(self.document.create_label(f"P{index}"), 32.0)
            boxes = []
            for axis, value in zip(("x", "y"), point, strict=True):
                box = self.document.create_spin_box(float(value))
                box.widget.debug_name = f"native-procedural-param-point-{index}-{axis}"
                box.set_range(-1.0e6, 1.0e6)
                box.step = 0.1
                box.decimals = 3
                boxes.append(box)
                row.add_stretch_child(box.widget)

            def changed(_value: float, point_index=index, controls=tuple(boxes)) -> None:
                point_value = (float(controls[0].value), float(controls[1].value))
                if kind == "contour":
                    self.model.set_contour_point(item.id, point_index, point_value)
                else:
                    self.model.set_path_point(item.id, point_index, point_value)

            for box in boxes:
                box.connect_changed(changed)
            self.param_host.add_fixed_child(row, self.metrics.compact_row)

    def _rebuild_primitive(self, operation) -> None:
        kind = str(operation.params.get("primitive_kind", ""))
        spec = primitive_spec(kind)
        if spec is None:
            _logger.error("Unknown native CSG primitive kind '%s'", kind)
            return
        self._append_title(f"{primitive_label(kind)} Parameters")
        for param in spec.param_schema:
            value = operation.params.get(param.key, param.default)
            minimum = -1.0e6 if param.min_value is None else float(param.min_value)
            maximum = 1.0e6 if param.max_value is None else float(param.max_value)
            if param.kind == "vec3":
                self._append_vector(
                    param.key,
                    param.label,
                    self._vector(operation.params, param.key, param.default),
                    lambda updated, key=param.key: self.model.set_primitive_params(operation.id, {key: list(updated)}),
                )
            elif param.kind in ("float", "int"):
                self._append_scalar(
                    param.key,
                    param.label,
                    float(value),
                    lambda updated, key=param.key: self.model.set_primitive_params(operation.id, {key: updated}),
                    min_value=minimum,
                    max_value=maximum,
                    integer=param.kind == "int",
                )
            elif param.kind == "bool":
                checkbox = self.document.create_checkbox(bool(value))
                checkbox.widget.debug_name = f"native-procedural-param-{param.key}"
                checkbox.connect_changed(
                    lambda checked, key=param.key: self.model.set_primitive_params(operation.id, {key: bool(checked)})
                )
                row = self.document.create_hstack(f"native-procedural-param-row-{param.key}")
                row.set_layout_spacing(self.metrics.dense_spacing)
                row.add_fixed_child(checkbox.widget, 24.0)
                row.add_stretch_child(
                    self.document.create_label(param.label, f"native-procedural-param-label-{param.key}")
                )
                self.param_host.add_fixed_child(row, 26.0)
            else:
                _logger.error(
                    "Unsupported native CSG primitive param kind '%s' for '%s'",
                    param.kind,
                    param.key,
                )

    def _rebuild_operation(self, operation) -> None:
        self._append_title(f"{operation.kind.title()} Parameters")
        if operation.kind == OPERATION_KIND_EXTRUDE:
            self._append_vector(
                "vector",
                "Extrude Vector",
                self._vector(operation.params, "vector", (0.0, 0.0, 1.0)),
                lambda value: self.model.set_extrude_vector(operation.id, value),
            )
        elif operation.kind == OPERATION_KIND_WALL:
            self._rebuild_wall(operation)

        def update_transform(key: str, value: tuple[float, float, float]) -> None:
            center = self._vector(operation.params, "center", (0.0, 0.0, 0.0))
            rotation = self._vector(operation.params, "rotation", (0.0, 0.0, 0.0))
            if key == "center":
                center = value
            else:
                rotation = value
            self.model.set_operation_transform(operation.id, center, rotation)

        self._append_vector(
            "center",
            "Center",
            self._vector(operation.params, "center", (0.0, 0.0, 0.0)),
            lambda value: update_transform("center", value),
        )
        self._append_vector(
            "rotation",
            "Rotation",
            self._vector(operation.params, "rotation", (0.0, 0.0, 0.0)),
            lambda value: update_transform("rotation", value),
        )

    def _rebuild_wall(self, operation) -> None:
        def update(
            *,
            height: float | None = None,
            thickness: float | None = None,
            alignment: str | None = None,
        ) -> None:
            self.model.set_wall_params(
                operation.id,
                float(operation.params.get("height", 3.0)) if height is None else height,
                float(operation.params.get("thickness", 0.2)) if thickness is None else thickness,
                str(operation.params.get("alignment", "center")) if alignment is None else alignment,
            )

        self._append_scalar(
            "height",
            "Height",
            float(operation.params.get("height", 3.0)),
            lambda value: update(height=value),
        )
        self._append_scalar(
            "thickness",
            "Thickness",
            float(operation.params.get("thickness", 0.2)),
            lambda value: update(thickness=value),
        )
        alignment = self.document.create_status_bar(f"Alignment: {operation.params.get('alignment', 'center')}")
        alignment.widget.debug_name = "native-procedural-param-alignment"
        self.param_host.add_fixed_child(alignment.widget, 20.0)
        row = self.document.create_hstack("native-procedural-param-alignment-row")
        row.set_layout_spacing(self.metrics.dense_spacing)
        for value, label in (("center", "Center"), ("left", "Left"), ("right", "Right")):
            button = self.document.create_button(label, f"native-procedural-param-alignment-{value}")
            button.connect_clicked(lambda next_value=value: update(alignment=next_value))
            row.add_stretch_child(button.widget)
        self.param_host.add_fixed_child(row, self.metrics.compact_row)
        sketch_id = str(operation.params.get("source_sketch_id", ""))
        sketch = self.model.controller.document.find_sketch(sketch_id)
        if sketch is None:
            return
        base_height = float(operation.params.get("height", 3.0))
        input_ids = set(operation.inputs)

        def append_offsets(source_id: str, label: str, count: int) -> None:
            offsets = wall_corner_height_offsets(
                operation.params,
                source_id,
                count,
                operation_id=operation.id,
            )
            for index, offset in enumerate(offsets):
                self._append_scalar(
                    f"wall-offset-{source_id}-{index}",
                    f"{label} P{index}",
                    offset,
                    lambda value, point_index=index, source=source_id: self.model.set_wall_corner_offset(
                        operation.id, source, point_index, value
                    ),
                    min_value=MIN_WALL_CORNER_HEIGHT - base_height,
                )

        for path in sketch.paths:
            if path.id in input_ids:
                append_offsets(path.id, "Path", len(path.points))
        for contour in sketch.outer_contours():
            if contour.id in input_ids and not sketch.hole_contours_for_outer(contour.id):
                append_offsets(contour.id, "Contour", len(contour.points))


def build_native_csg_editor_panel(
    document: TcDocument,
    model,
    *,
    metrics: NativeCsgPanelMetrics = DEFAULT_NATIVE_CSG_PANEL_METRICS,
    separate: bool = False,
    viewport: Callable[[], Rect] | None = None,
) -> NativeCsgEditorPanel:
    """Build a native CSG tree and inspector around a toolkit-neutral command facade."""

    inspector = document.create_vstack("native-procedural-mesh-extension")
    inspector.stable_id = "editor.inspector.extension.procedural-mesh"
    inspector.set_layout_padding(metrics.embedded_panel_insets)
    inspector.set_layout_spacing(metrics.spacing)
    inspector.preferred_size = Size(340.0, 702.0)
    title = document.create_label("Procedural Geometry", "native-procedural-title")
    mode = document.create_status_bar("Mode: idle; draft points: 0")
    mode.widget.debug_name = "native-procedural-mode"
    summary = document.create_status_bar("Document: <empty>")
    summary.widget.debug_name = "native-procedural-summary"
    selection = document.create_status_bar("Selection: <none>")
    selection.widget.debug_name = "native-procedural-selection"
    status = document.create_status_bar("Status: Ready")
    status.widget.debug_name = "native-procedural-status"
    inspector.add_fixed_child(title, metrics.section_row)
    inspector.add_fixed_child(mode.widget, metrics.compact_status_row)
    inspector.add_fixed_child(summary.widget, metrics.compact_status_row)
    inspector.add_fixed_child(selection.widget, metrics.compact_status_row)

    action_host = document.create_vstack("native-procedural-context-actions")
    action_host.set_layout_spacing(metrics.dense_spacing)
    action_host.visible = False
    inspector.add_fixed_child(action_host, 146.0)

    tool_row = document.create_hstack("native-procedural-tool-row")
    tool_row.set_layout_spacing(metrics.spacing)
    for label, name, callback in (
        ("Draw", "draw", model.start_draw_sketch),
        ("Close", "close", model.close_contour),
        ("Finish", "finish", model.finish_wall_path),
        ("Stop", "stop", model.clear_tool),
    ):
        button = document.create_button(label, f"native-procedural-{name}")
        button.connect_clicked(callback)
        tool_row.add_stretch_child(button.widget)
    inspector.add_fixed_child(tool_row, metrics.compact_row)

    primitive_row = document.create_hstack("native-procedural-primitive-row")
    primitive_row.set_layout_spacing(metrics.spacing)
    for spec in ordered_primitive_specs():
        button = document.create_button(spec.label, f"native-procedural-primitive-{spec.kind}")
        button.connect_clicked(lambda kind=spec.kind: model.add_primitive(kind))
        primitive_row.add_stretch_child(button.widget)
    inspector.add_fixed_child(primitive_row, metrics.compact_row)

    operation_row = document.create_hstack("native-procedural-operation-row")
    operation_row.set_layout_spacing(metrics.spacing)
    for spec in ordered_boolean_operation_specs():
        button = document.create_button(spec.label, f"native-procedural-boolean-{spec.kind}")
        button.connect_clicked(lambda kind=spec.kind: model.add_boolean_operation(kind))
        operation_row.add_stretch_child(button.widget)
    inspector.add_fixed_child(operation_row, metrics.compact_row)

    direct_row = document.create_hstack("native-procedural-action-row")
    direct_row.set_layout_spacing(metrics.spacing)
    for label, name, callback in (
        ("Extrude", "extrude", model.extrude_selected),
        ("Wall", "wall", model.wall_selected),
        ("Clear", "clear", model.clear_document),
    ):
        button = document.create_button(label, f"native-procedural-{name}")
        button.connect_clicked(callback)
        direct_row.add_stretch_child(button.widget)
    inspector.add_fixed_child(direct_row, metrics.compact_row)

    param_host = document.create_vstack("native-procedural-param-host")
    param_host.set_layout_spacing(metrics.dense_spacing)
    param_host.set_layout_padding(metrics.embedded_panel_insets)
    param_host.visible = False
    param_scroll = document.create_scroll_area("native-procedural-param-scroll")
    param_scroll.set_scroll_axes(False, True)
    param_scroll.set_content(param_host)
    inspector.add_stretch_child(param_scroll.widget)
    inspector.add_fixed_child(status.widget, metrics.compact_status_row)

    tree_model = TreeModel()
    expansion = TreeExpansionModel()
    tree = document.create_tree_widget(tree_model, expansion)
    tree.widget.debug_name = "native-procedural-document-tree"
    tree.draggable = True
    tree.set_row_height(22.0)
    tree.set_row_spacing(1.0)
    tree_root = document.create_vstack("native-procedural-tree-root")
    tree_root.stable_id = "csg.document-tree"
    tree_root.set_layout_padding(metrics.embedded_panel_insets)
    tree_root.set_layout_spacing(metrics.spacing)
    tree_root.preferred_size = Size(340.0, 176.0)
    tree_root.add_fixed_child(
        document.create_label("Document Tree", "native-procedural-tree-title"),
        metrics.section_row,
    )
    tree_root.add_stretch_child(tree.widget)

    context_model = CommandModel()
    context_menu = document.create_menu(context_model)
    combined = None
    if not separate:
        combined = document.create_vstack("native-csg-editor-panel")
        combined.stable_id = "editor.inspector.extension.procedural-mesh"
        combined.preferred_size = Size(340.0, 702.0)
        combined.set_layout_padding(metrics.embedded_panel_insets)
        combined.set_layout_spacing(metrics.spacing)
        combined.add_fixed_child(tree_root, 176.0)
        combined.add_stretch_child(inspector)
    panel = NativeCsgEditorPanel(
        document=document,
        model=model,
        root=combined,
        tree_root=tree_root,
        inspector_root=inspector,
        tree=tree,
        tree_model=tree_model,
        tree_expansion=expansion,
        mode_label=mode,
        summary_label=summary,
        selection_label=selection,
        status_label=status,
        action_host=action_host,
        param_host=param_host,
        context_model=context_model,
        context_menu=context_menu,
        viewport=viewport or (lambda: (combined or inspector).bounds),
        metrics=metrics,
    )
    tree.connect_selection_changed(panel.select_tree_node)
    tree.connect_expansion_changed(panel.set_expanded)
    tree.connect_context_menu_requested(panel.show_context_menu)
    tree.connect_drop_requested(panel.drop_node)
    context_menu.connect_activated(lambda _index, _command_id, command: panel.execute_context_action(command.stable_id))
    model.set_changed_handler(panel.apply_snapshot)
    return panel


__all__ = [
    "DEFAULT_NATIVE_CSG_PANEL_METRICS",
    "NativeCsgEditorPanel",
    "NativeCsgPanelMetrics",
    "build_native_csg_editor_panel",
]
