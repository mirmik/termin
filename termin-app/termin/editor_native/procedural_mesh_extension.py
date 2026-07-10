"""Native projection for the toolkit-neutral ProceduralMesh extension model."""

from __future__ import annotations

import logging

from termin.editor_core.component_editor_extension import (
    ComponentEditorExtension,
    ComponentExtensionPresentation,
)
from termin.gui_native import (
    CollectionItem,
    Document,
    EdgeInsets,
    Size,
    TreeExpansionModel,
    TreeModel,
)


_logger = logging.getLogger(__name__)


def project_native_procedural_mesh_extension(
    extension: ComponentEditorExtension,
    document: Document,
) -> ComponentExtensionPresentation:
    from termin.csg.operation_specs import (
        ordered_boolean_operation_specs,
        ordered_primitive_specs,
    )
    from termin.editor_core.procedural_mesh_editor_extension import (
        ProceduralMeshExtensionModel,
    )

    if not isinstance(extension, ProceduralMeshExtensionModel):
        _logger.error("ProceduralMesh projector received incompatible extension")
        raise TypeError("procedural mesh projector requires ProceduralMeshExtensionModel")

    root = document.create_vstack("native-procedural-mesh-extension")
    root.stable_id = "editor.inspector.extension.procedural-mesh"
    root.set_layout_padding(EdgeInsets(2.0, 2.0, 2.0, 2.0))
    root.set_layout_spacing(4.0)
    root.preferred_size = Size(340.0, 702.0)

    title = document.create_label("Procedural Geometry", "native-procedural-title")
    mode = document.create_status_bar("Mode: idle; draft points: 0")
    mode.widget.debug_name = "native-procedural-mode"
    summary = document.create_status_bar("Document: <empty>")
    summary.widget.debug_name = "native-procedural-summary"
    selection = document.create_status_bar("Selection: <none>")
    selection.widget.debug_name = "native-procedural-selection"
    status = document.create_status_bar("Status: Ready")
    status.widget.debug_name = "native-procedural-status"
    root.add_fixed_child(title, 24.0)
    root.add_fixed_child(mode.widget, 22.0)
    root.add_fixed_child(summary.widget, 22.0)
    root.add_fixed_child(selection.widget, 22.0)

    tree_model = TreeModel()
    tree_expansion = TreeExpansionModel()
    tree = document.create_tree_widget(tree_model, tree_expansion)
    tree.widget.debug_name = "native-procedural-document-tree"
    tree.set_row_height(22.0)
    tree.set_row_spacing(1.0)
    root.add_fixed_child(tree.widget, 176.0)
    tree_selections: dict[int, tuple[str, str]] = {}
    tree_keys: dict[int, str] = {}
    collapsed_keys: set[str] = set()
    applying_snapshot = False

    tool_row = document.create_hstack("native-procedural-tool-row")
    tool_row.set_layout_spacing(4.0)
    draw = document.create_button("Draw", "native-procedural-draw")
    close = document.create_button("Close", "native-procedural-close")
    finish = document.create_button("Finish", "native-procedural-finish")
    clear_tool = document.create_button("Stop", "native-procedural-stop")
    tool_row.add_stretch_child(draw.widget)
    tool_row.add_stretch_child(close.widget)
    tool_row.add_stretch_child(finish.widget)
    tool_row.add_stretch_child(clear_tool.widget)
    root.add_fixed_child(tool_row, 28.0)

    primitive_row = document.create_hstack("native-procedural-primitive-row")
    primitive_row.set_layout_spacing(4.0)
    for spec in ordered_primitive_specs():
        button = document.create_button(spec.label, f"native-procedural-primitive-{spec.kind}")
        button.connect_clicked(lambda kind=spec.kind: extension.add_primitive(kind))
        primitive_row.add_stretch_child(button.widget)
    root.add_fixed_child(primitive_row, 28.0)

    operation_row = document.create_hstack("native-procedural-operation-row")
    operation_row.set_layout_spacing(4.0)
    for spec in ordered_boolean_operation_specs():
        button = document.create_button(spec.label, f"native-procedural-boolean-{spec.kind}")
        button.connect_clicked(lambda kind=spec.kind: extension.add_boolean_operation(kind))
        operation_row.add_stretch_child(button.widget)
    root.add_fixed_child(operation_row, 28.0)

    action_row = document.create_hstack("native-procedural-action-row")
    action_row.set_layout_spacing(4.0)
    extrude = document.create_button("Extrude", "native-procedural-extrude")
    wall = document.create_button("Wall", "native-procedural-wall")
    clear = document.create_button("Clear", "native-procedural-clear")
    action_row.add_stretch_child(extrude.widget)
    action_row.add_stretch_child(wall.widget)
    action_row.add_stretch_child(clear.widget)
    root.add_fixed_child(action_row, 28.0)

    param_host = document.create_vstack("native-procedural-param-host")
    param_host.set_layout_spacing(3.0)
    param_host.set_layout_padding(EdgeInsets(2.0, 2.0, 2.0, 2.0))
    param_host.visible = False
    param_scroll = document.create_scroll_area("native-procedural-param-scroll")
    param_scroll.set_content(param_host)
    root.add_fixed_child(param_scroll.widget, 270.0)
    root.add_fixed_child(status.widget, 22.0)

    def clear_param_host() -> None:
        for child in tuple(param_host.children):
            if not document.destroy_widget_recursive(child.handle):
                raise RuntimeError("failed to destroy native ProceduralMesh parameter row")

    def vector_param(params: dict, key: str, default) -> tuple[float, float, float]:
        value = params.get(key, default)
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (IndexError, TypeError, ValueError):
            return (float(default[0]), float(default[1]), float(default[2]))

    def rebuild_plane_params(sketch) -> None:
        from termin.csg.procedural_document import ProceduralPlane

        param_host.visible = True
        param_host.add_fixed_child(
            document.create_label(
                f"Plane: {sketch.name}",
                "native-procedural-param-title",
            ),
            22.0,
        )
        groups: dict[str, tuple] = {}
        for key, label, values in (
            ("origin", "Origin", sketch.plane.origin),
            ("x-axis", "X Axis", sketch.plane.x_axis),
            ("y-axis", "Y Axis", sketch.plane.y_axis),
        ):
            param_host.add_fixed_child(
                document.create_label(label, f"native-procedural-param-label-{key}"),
                20.0,
            )
            row = document.create_hstack(f"native-procedural-param-row-{key}")
            row.set_layout_spacing(2.0)
            boxes = []
            for axis, value in zip(("x", "y", "z"), values, strict=True):
                box = document.create_spin_box(float(value))
                box.widget.debug_name = f"native-procedural-param-{key}-{axis}"
                box.set_range(-1.0e6, 1.0e6)
                box.step = 0.1
                box.decimals = 3
                boxes.append(box)
                row.add_stretch_child(box.widget)
            groups[key] = tuple(boxes)
            param_host.add_fixed_child(row, 28.0)

        def plane_changed(_value: float) -> None:
            def values(key: str) -> tuple[float, float, float]:
                return tuple(float(control.value) for control in groups[key])

            extension.set_sketch_plane(
                sketch.id,
                ProceduralPlane(
                    origin=values("origin"),
                    x_axis=values("x-axis"),
                    y_axis=values("y-axis"),
                ),
            )

        for controls in groups.values():
            for control in controls:
                control.connect_changed(plane_changed)

    def rebuild_point_params(kind: str, item) -> None:
        param_host.visible = True
        title = "Contour" if kind == "contour" else "Path"
        param_host.add_fixed_child(
            document.create_label(
                f"{title}: {item.name}",
                "native-procedural-param-title",
            ),
            22.0,
        )
        for index, point in enumerate(item.points):
            row = document.create_hstack(f"native-procedural-param-row-point-{index}")
            row.set_layout_spacing(3.0)
            row.add_fixed_child(document.create_label(f"P{index}"), 32.0)
            boxes = []
            for axis, value in zip(("x", "y"), point, strict=True):
                box = document.create_spin_box(float(value))
                box.widget.debug_name = f"native-procedural-param-point-{index}-{axis}"
                box.set_range(-1.0e6, 1.0e6)
                box.step = 0.1
                box.decimals = 3
                boxes.append(box)
                row.add_stretch_child(box.widget)

            def point_changed(
                _value: float,
                point_index=index,
                controls=tuple(boxes),
            ) -> None:
                updated = (float(controls[0].value), float(controls[1].value))
                if kind == "contour":
                    extension.set_contour_point(item.id, point_index, updated)
                else:
                    extension.set_path_point(item.id, point_index, updated)

            for box in boxes:
                box.connect_changed(point_changed)
            param_host.add_fixed_child(row, 28.0)

    def rebuild_operation_params(operation) -> bool:
        from termin.csg.operation_specs import (
            BOOLEAN_OPERATION_KINDS,
            OPERATION_KIND_EXTRUDE,
            OPERATION_KIND_WALL,
        )

        if operation.kind not in {
            OPERATION_KIND_EXTRUDE,
            OPERATION_KIND_WALL,
            *BOOLEAN_OPERATION_KINDS,
        }:
            return False
        param_host.visible = True
        param_host.add_fixed_child(
            document.create_label(
                f"{operation.kind.title()} Parameters",
                "native-procedural-param-title",
            ),
            22.0,
        )

        def append_vector(key: str, label: str, values, changed) -> None:
            param_host.add_fixed_child(
                document.create_label(label, f"native-procedural-param-label-{key}"),
                20.0,
            )
            row = document.create_hstack(f"native-procedural-param-row-{key}")
            row.set_layout_spacing(2.0)
            boxes = []
            for axis, value in zip(("x", "y", "z"), values, strict=True):
                box = document.create_spin_box(value)
                box.widget.debug_name = f"native-procedural-param-{key}-{axis}"
                box.set_range(-1.0e6, 1.0e6)
                box.step = 0.1
                box.decimals = 3
                boxes.append(box)
                row.add_stretch_child(box.widget)

            def vector_changed(_value: float, controls=tuple(boxes)) -> None:
                changed(tuple(float(control.value) for control in controls))

            for box in boxes:
                box.connect_changed(vector_changed)
            param_host.add_fixed_child(row, 28.0)

        def append_scalar(
            key: str,
            label: str,
            value: float,
            changed,
            *,
            min_value: float = 0.001,
        ) -> None:
            row = document.create_hstack(f"native-procedural-param-row-{key}")
            row.set_layout_spacing(3.0)
            row.add_fixed_child(
                document.create_label(label, f"native-procedural-param-label-{key}"),
                104.0,
            )
            box = document.create_spin_box(value)
            box.widget.debug_name = f"native-procedural-param-{key}"
            box.set_range(min_value, 1.0e6)
            box.step = 0.1
            box.decimals = 3
            box.connect_changed(lambda updated: changed(float(updated)))
            row.add_stretch_child(box.widget)
            param_host.add_fixed_child(row, 28.0)

        if operation.kind == OPERATION_KIND_EXTRUDE:
            append_vector(
                "vector",
                "Extrude Vector",
                vector_param(operation.params, "vector", (0.0, 0.0, 1.0)),
                lambda value: extension.set_extrude_vector(operation.id, value),
            )
        elif operation.kind == OPERATION_KIND_WALL:
            def update_wall(
                *,
                height: float | None = None,
                thickness: float | None = None,
                alignment: str | None = None,
            ) -> None:
                extension.set_wall_params(
                    operation.id,
                    float(operation.params.get("height", 3.0)) if height is None else height,
                    (
                        float(operation.params.get("thickness", 0.2))
                        if thickness is None
                        else thickness
                    ),
                    (
                        str(operation.params.get("alignment", "center"))
                        if alignment is None
                        else alignment
                    ),
                )

            append_scalar(
                "height",
                "Height",
                float(operation.params.get("height", 3.0)),
                lambda value: update_wall(height=value),
            )
            append_scalar(
                "thickness",
                "Thickness",
                float(operation.params.get("thickness", 0.2)),
                lambda value: update_wall(thickness=value),
            )
            alignment = document.create_status_bar(
                f"Alignment: {operation.params.get('alignment', 'center')}"
            )
            alignment.widget.debug_name = "native-procedural-param-alignment"
            param_host.add_fixed_child(alignment.widget, 20.0)
            alignment_row = document.create_hstack("native-procedural-param-alignment-row")
            alignment_row.set_layout_spacing(3.0)
            for value, label in (("center", "Center"), ("left", "Left"), ("right", "Right")):
                button = document.create_button(
                    label,
                    f"native-procedural-param-alignment-{value}",
                )
                button.connect_clicked(lambda next_value=value: update_wall(alignment=next_value))
                alignment_row.add_stretch_child(button.widget)
            param_host.add_fixed_child(alignment_row, 28.0)

            from termin.csg.wall_height_offsets import (
                MIN_WALL_CORNER_HEIGHT,
                wall_corner_height_offsets,
            )

            source_sketch_id = str(operation.params.get("source_sketch_id", ""))
            sketch = extension.controller.document.find_sketch(source_sketch_id)
            if sketch is not None:
                base_height = float(operation.params.get("height", 3.0))
                input_ids = set(operation.inputs)

                def append_offsets(source_id: str, label: str, point_count: int) -> None:
                    offsets = wall_corner_height_offsets(
                        operation.params,
                        source_id,
                        point_count,
                        operation_id=operation.id,
                    )
                    for index, offset in enumerate(offsets):
                        append_scalar(
                            f"wall-offset-{source_id}-{index}",
                            f"{label} P{index}",
                            offset,
                            lambda value, i=index, source=source_id: (
                                extension.set_wall_corner_offset(
                                    operation.id,
                                    source,
                                    i,
                                    value,
                                )
                            ),
                            min_value=MIN_WALL_CORNER_HEIGHT - base_height,
                        )

                for path in sketch.paths:
                    if path.id in input_ids:
                        append_offsets(path.id, "Path", len(path.points))
                for contour in sketch.outer_contours():
                    if contour.id in input_ids and not sketch.hole_contours_for_outer(contour.id):
                        append_offsets(contour.id, "Contour", len(contour.points))

        def update_transform(key: str, value: tuple[float, float, float]) -> None:
            center = vector_param(operation.params, "center", (0.0, 0.0, 0.0))
            rotation = vector_param(operation.params, "rotation", (0.0, 0.0, 0.0))
            if key == "center":
                center = value
            else:
                rotation = value
            extension.set_operation_transform(operation.id, center, rotation)

        append_vector(
            "center",
            "Center",
            vector_param(operation.params, "center", (0.0, 0.0, 0.0)),
            lambda value: update_transform("center", value),
        )
        append_vector(
            "rotation",
            "Rotation",
            vector_param(operation.params, "rotation", (0.0, 0.0, 0.0)),
            lambda value: update_transform("rotation", value),
        )
        return True

    def rebuild_params() -> None:
        from termin.csg.operation_specs import PRIMITIVE_OPERATION_KIND, primitive_label, primitive_spec

        clear_param_host()
        current_selection = extension.controller.selection
        if current_selection is None:
            param_host.visible = False
            return
        selection_kind, selection_id = current_selection
        if selection_kind == "plane":
            sketch = extension.controller.document.find_sketch(selection_id)
            if sketch is None:
                param_host.visible = False
            else:
                rebuild_plane_params(sketch)
            return
        if selection_kind == "contour":
            contour_ref = extension.controller.document.find_contour_ref(selection_id)
            if contour_ref is None:
                param_host.visible = False
            else:
                rebuild_point_params("contour", contour_ref[1])
            return
        if selection_kind == "path":
            path_ref = extension.controller.document.find_path_ref(selection_id)
            if path_ref is None:
                param_host.visible = False
            else:
                rebuild_point_params("path", path_ref[1])
            return
        if selection_kind != "operation":
            param_host.visible = False
            return
        operation = extension.controller.document.find_operation(selection_id)
        if operation is None:
            param_host.visible = False
            return
        if operation.kind != PRIMITIVE_OPERATION_KIND:
            if not rebuild_operation_params(operation):
                param_host.visible = False
            return
        primitive_kind = str(operation.params.get("primitive_kind", ""))
        spec = primitive_spec(primitive_kind)
        if spec is None:
            _logger.error("Unknown ProceduralMesh primitive kind '%s'", primitive_kind)
            param_host.visible = False
            return

        param_host.visible = True
        param_host.add_fixed_child(
            document.create_label(
                f"{primitive_label(primitive_kind)} Parameters",
                "native-procedural-param-title",
            ),
            22.0,
        )
        for param in spec.param_schema:
            if param.kind == "vec3":
                param_host.add_fixed_child(
                    document.create_label(
                        param.label,
                        f"native-procedural-param-label-{param.key}",
                    ),
                    20.0,
                )
                row = document.create_hstack(f"native-procedural-param-row-{param.key}")
                row.set_layout_spacing(2.0)
                values = vector_param(operation.params, param.key, param.default)
                boxes = []
                for axis, value in zip(("x", "y", "z"), values, strict=True):
                    box = document.create_spin_box(value)
                    box.widget.debug_name = f"native-procedural-param-{param.key}-{axis}"
                    box.set_range(
                        -1.0e6 if param.min_value is None else float(param.min_value),
                        1.0e6 if param.max_value is None else float(param.max_value),
                    )
                    box.step = 0.1
                    box.decimals = 3
                    boxes.append(box)
                    row.add_stretch_child(box.widget)

                def vector_changed(
                    _value: float,
                    operation_id=operation.id,
                    key=param.key,
                    controls=tuple(boxes),
                ) -> None:
                    extension.set_primitive_params(
                        operation_id,
                        {key: [control.value for control in controls]},
                    )

                for box in boxes:
                    box.connect_changed(vector_changed)
                param_host.add_fixed_child(row, 28.0)
                continue
            if param.kind in ("float", "int"):
                row = document.create_hstack(f"native-procedural-param-row-{param.key}")
                row.set_layout_spacing(3.0)
                row.add_fixed_child(
                    document.create_label(
                        param.label,
                        f"native-procedural-param-label-{param.key}",
                    ),
                    104.0,
                )
                box = document.create_spin_box(float(operation.params.get(param.key, param.default)))
                box.widget.debug_name = f"native-procedural-param-{param.key}"
                box.set_range(
                    -1.0e6 if param.min_value is None else float(param.min_value),
                    1.0e6 if param.max_value is None else float(param.max_value),
                )
                box.step = 1.0 if param.kind == "int" else 0.1
                box.decimals = 0 if param.kind == "int" else 3

                def scalar_changed(
                    value: float,
                    operation_id=operation.id,
                    key=param.key,
                    integer=param.kind == "int",
                ) -> None:
                    updated = int(round(value)) if integer else float(value)
                    extension.set_primitive_params(operation_id, {key: updated})

                box.connect_changed(scalar_changed)
                row.add_stretch_child(box.widget)
                param_host.add_fixed_child(row, 28.0)
                continue
            if param.kind == "bool":
                checkbox = document.create_checkbox(bool(operation.params.get(param.key, param.default)))
                checkbox.widget.debug_name = f"native-procedural-param-{param.key}"

                def bool_changed(
                    value: bool,
                    operation_id=operation.id,
                    key=param.key,
                ) -> None:
                    extension.set_primitive_params(operation_id, {key: bool(value)})

                checkbox.connect_changed(bool_changed)
                row = document.create_hstack(f"native-procedural-param-row-{param.key}")
                row.set_layout_spacing(3.0)
                row.add_fixed_child(checkbox.widget, 24.0)
                row.add_stretch_child(
                    document.create_label(
                        param.label,
                        f"native-procedural-param-label-{param.key}",
                    )
                )
                param_host.add_fixed_child(row, 26.0)
                continue
            _logger.error(
                "Unsupported ProceduralMesh primitive param kind '%s' for '%s'",
                param.kind,
                param.key,
            )

    def apply_snapshot(snapshot) -> None:
        nonlocal applying_snapshot
        mode.text = f"Mode: {snapshot.mode}; draft points: {snapshot.draft_point_count}"
        summary.text = snapshot.document_summary
        if snapshot.selection is None:
            selection.text = "Selection: <none>"
        else:
            selection.text = f"Selection: {snapshot.selection[0]} {snapshot.selection[1][:10]}"
        status.text = f"Status: {snapshot.status}"
        mode.widget.name = mode.text
        summary.widget.name = summary.text
        selection.widget.name = selection.text
        status.widget.name = status.text

        from termin.csg.document_tree_model import build_document_tree

        applying_snapshot = True
        try:
            tree_model.clear()
            tree_expansion.clear()
            tree_selections.clear()
            tree_keys.clear()
            selected_node = None

            def append_node(source, parent: int | None, path: str) -> None:
                nonlocal selected_node
                segment = f"{source.kind}:{source.item_id}"
                if source.input_index >= 0:
                    segment = f"{segment}@{source.input_index}"
                stable_key = f"{path}/{segment}"
                item = CollectionItem(stable_key, source.text, source.kind)
                if source.kind == "info":
                    item.enabled = False
                node = (
                    tree_model.append_root(item)
                    if parent is None
                    else tree_model.append_child(parent, item)
                )
                tree_keys[node] = stable_key
                if source.kind != "info":
                    node_selection = (source.kind, source.item_id)
                    tree_selections[node] = node_selection
                    if node_selection == snapshot.selection and selected_node is None:
                        selected_node = node
                if source.children and stable_key not in collapsed_keys:
                    tree_expansion.set_expanded(node, True)
                for child in source.children:
                    append_node(child, node, stable_key)

            for source in build_document_tree(extension.controller.document):
                append_node(source, None, "document")
            if selected_node is None:
                tree.clear_selection()
            else:
                tree.select(selected_node, reveal=True)
        finally:
            applying_snapshot = False
        rebuild_params()

    def on_tree_selection(node: int) -> None:
        if applying_snapshot:
            return
        node_selection = tree_selections.get(node)
        if node_selection is not None:
            extension.select_node(node_selection)

    def on_tree_expansion(node: int, expanded: bool) -> None:
        if applying_snapshot:
            return
        stable_key = tree_keys.get(node)
        if stable_key is None:
            return
        if expanded:
            collapsed_keys.discard(stable_key)
        else:
            collapsed_keys.add(stable_key)

    draw.connect_clicked(extension.start_draw_sketch)
    close.connect_clicked(extension.close_contour)
    finish.connect_clicked(extension.finish_wall_path)
    clear_tool.connect_clicked(extension.clear_tool)
    extrude.connect_clicked(extension.extrude_selected)
    wall.connect_clicked(extension.wall_selected)
    clear.connect_clicked(extension.clear_document)
    tree.connect_selection_changed(on_tree_selection)
    tree.connect_expansion_changed(on_tree_expansion)
    extension.set_changed_handler(apply_snapshot)
    return ComponentExtensionPresentation(right_panel=root)


__all__ = ["project_native_procedural_mesh_extension"]
