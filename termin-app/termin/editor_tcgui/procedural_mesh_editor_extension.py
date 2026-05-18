"""tcgui editor extension for ProceduralMeshComponent."""

from __future__ import annotations

from tcbase import log
from tcbase._geom_native import Vec3
from tgfx._tgfx_native import Color4
from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.vstack import VStack
from tcgui.widgets.units import px

from termin.editor_tcgui.component_editor_extension import (
    register_component_editor_extension,
)


class ProceduralMeshEditorExtension:
    def __init__(self) -> None:
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._component = None
        self._mode = "idle"
        self._mode_label = Label()
        self._document_summary_label = Label()
        self._selection_label = Label()
        self._document_tree = TreeWidget()
        self._selected_node_data: tuple[str, str] | None = None
        self._draft_points: list[tuple[float, float, float]] = []

    def attach(self, editor, entity, component_ref) -> None:
        self._editor = editor
        self._entity = entity
        self._component_ref = component_ref
        self._component = component_ref.to_python()
        if self._component is None:
            log.error("[ProceduralMeshEditor] failed to resolve ProceduralMeshComponent object")
        editor.add_viewport_click_interceptor(self._on_viewport_click)
        editor.add_viewport_overlay_drawer(self._draw_overlay)
        log.info("[ProceduralMeshEditor] extension attached")

    def detach(self) -> None:
        editor = self._editor
        if editor is not None:
            editor.remove_viewport_click_interceptor(self._on_viewport_click)
            editor.remove_viewport_overlay_drawer(self._draw_overlay)
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._component = None
        self._mode = "idle"
        self._draft_points = []
        log.info("[ProceduralMeshEditor] extension detached")

    def build_panel(self):
        root = VStack()
        root.spacing = 4

        title = Label()
        title.text = "Procedural Geometry"
        root.add_child(title)

        self._mode_label.text = self._mode_text()
        self._mode_label.color = (0.55, 0.60, 0.68, 1.0)
        root.add_child(self._mode_label)

        row = HStack()
        row.spacing = 4
        row.preferred_height = px(28)
        row.add_child(self._make_button("Draw Sketch", "draw_sketch"))
        close_btn = Button()
        close_btn.text = "Close Contour"
        close_btn.on_click = self._close_contour
        row.add_child(close_btn)
        root.add_child(row)

        row2 = HStack()
        row2.spacing = 4
        row2.preferred_height = px(28)
        extrude_btn = Button()
        extrude_btn.text = "Extrude"
        extrude_btn.on_click = self._add_extrude_operation
        row2.add_child(extrude_btn)
        clear_btn = Button()
        clear_btn.text = "Clear Sketch"
        clear_btn.on_click = self._clear_sketch
        row2.add_child(clear_btn)
        row2.add_child(self._make_button("Clear Tool", "idle"))
        root.add_child(row2)

        doc_title = Label()
        doc_title.text = "Document Tree"
        root.add_child(doc_title)

        self._document_summary_label.text = "Document: <empty>"
        self._document_summary_label.color = (0.55, 0.60, 0.68, 1.0)
        root.add_child(self._document_summary_label)

        self._selection_label.text = "Selection: <none>"
        self._selection_label.color = (0.55, 0.60, 0.68, 1.0)
        root.add_child(self._selection_label)

        self._document_tree.row_height = 22
        self._document_tree.indent_size = 22
        self._document_tree.preferred_height = px(180)
        self._document_tree.stretch = True
        self._document_tree.on_select = self._on_document_node_selected
        root.add_child(self._document_tree)
        self._refresh_document_tree()

        return root

    def _make_button(self, text: str, mode: str) -> Button:
        btn = Button()
        btn.text = text
        btn.on_click = lambda m=mode: self._set_mode(m)
        return btn

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._mode_label.text = self._mode_text()
        self._request_viewport_update()
        log.info(f"[ProceduralMeshEditor] mode={mode}")

    def _mode_text(self) -> str:
        return (
            f"Mode: {self._mode}; "
            f"draft points: {len(self._draft_points)}; "
            f"contours: {self._document_contour_count()}"
        )

    def _refresh_mode_label(self) -> None:
        self._mode_label.text = self._mode_text()

    def _close_contour(self) -> None:
        if len(self._draft_points) < 3:
            log.error(
                "[ProceduralMeshEditor] cannot close contour: "
                f"need at least 3 points, got {len(self._draft_points)}"
            )
            return
        component = self._component
        if component is None:
            log.error("[ProceduralMeshEditor] cannot close contour: component object is not available")
            return
        if not component.add_contour_from_world_points(self._draft_points[:]):
            return
        if component.document.items:
            self._selected_node_data = ("sketch", component.document.items[0].id)
        self._draft_points = []
        self._refresh_mode_label()
        self._refresh_document_tree()
        self._request_viewport_update()
        log.info(
            "[ProceduralMeshEditor] contour closed "
            f"contours={self._document_contour_count()}"
        )

    def _add_extrude_operation(self) -> None:
        component = self._component
        if component is None:
            log.error("[ProceduralMeshEditor] cannot extrude: component object is not available")
            return
        node_data = self._selected_node_data
        if node_data is None or node_data[0] != "sketch":
            log.error("[ProceduralMeshEditor] cannot extrude: select a sketch node first")
            return
        sketch_id = node_data[1]
        if not component.add_extrude_operation_for_sketch(sketch_id, 1.0):
            return
        self._selected_node_data = ("operation", self._last_operation_id())
        self._refresh_mode_label()
        self._refresh_document_tree()
        self._request_viewport_update()
        log.info(f"[ProceduralMeshEditor] extrude operation added for sketch='{sketch_id}'")

    def _clear_sketch(self) -> None:
        component = self._component
        if component is not None:
            from termin.mesh.procedural_mesh_document import ProceduralMeshDocument

            component.document = ProceduralMeshDocument()
        self._draft_points = []
        self._selected_node_data = None
        self._refresh_mode_label()
        self._refresh_document_tree()
        self._request_viewport_update()
        log.info("[ProceduralMeshEditor] sketch cleared")

    def _document_contour_count(self) -> int:
        component = self._component
        if component is None:
            return 0
        return component.document.contour_count()

    def _refresh_document_tree(self) -> None:
        self._document_tree.clear()
        component = self._component
        if component is None:
            self._document_summary_label.text = "Document: <no component>"
            self._selection_label.text = "Selection: <none>"
            self._document_tree.add_root(self._tree_node("No component object", ("info", "none")))
            return

        document = component.document
        self._document_summary_label.text = (
            f"Document v{document.version}: sketches={len(document.items)}, "
            f"contours={document.contour_count()}, operations={len(document.operations)}"
        )

        used_sketch_ids = document.used_source_sketch_ids()
        roots: list[TreeNode] = []
        for operation in document.operations:
            op_node = self._operation_node(operation)
            source_sketch_id = str(operation.params.get("source_sketch_id", ""))
            if source_sketch_id:
                sketch = document.find_sketch(source_sketch_id)
                if sketch is not None:
                    op_node.add_node(self._sketch_node(sketch))
            roots.append(op_node)

        for item in document.items:
            if item.id not in used_sketch_ids:
                roots.append(self._sketch_node(item))

        if not roots:
            roots.append(self._tree_node("<empty>", ("info", "empty")))

        for node in roots:
            self._document_tree.add_root(node)
        self._restore_tree_selection(roots)
        self._refresh_selection_label()
        if self._document_tree._ui is not None:
            self._document_tree._ui.request_layout()

    def _tree_node(self, text: str, data: tuple[str, str]) -> TreeNode:
        label = Label()
        label.text = text
        label.color = (0.68, 0.72, 0.78, 1.0)
        node = TreeNode(label)
        node.data = data
        return node

    def _operation_node(self, operation) -> TreeNode:
        height_text = ""
        if operation.kind == "extrude" and "height" in operation.params:
            height_text = f" height={float(operation.params['height']):.3f}"
        node = self._tree_node(
            f"[Extrude] {operation.name}{height_text} inputs={len(operation.inputs)}",
            ("operation", operation.id),
        )
        node.expanded = True
        return node

    def _sketch_node(self, sketch) -> TreeNode:
        node = self._tree_node(
            f"[Sketch] {sketch.name} {self._short_id(sketch.id)} contours={len(sketch.contours)}",
            ("sketch", sketch.id),
        )
        node.expanded = True
        plane_node = self._tree_node(
            "[Plane] "
            f"origin={self._format_vec3(sketch.plane.origin)} "
            f"normal={self._format_vec3(sketch.plane.normal)}",
            ("plane", sketch.id),
        )
        node.add_node(plane_node)
        for contour in sketch.contours:
            node.add_node(
                self._tree_node(
                    f"[Contour] {contour.name} {self._short_id(contour.id)} points={len(contour.points)}",
                    ("contour", contour.id),
                )
            )
        return node

    def _restore_tree_selection(self, roots: list[TreeNode]) -> None:
        for root in roots:
            selected = self._find_tree_node(root, self._selected_node_data)
            if selected is not None:
                self._document_tree.selected_node = selected
                selected._selected = True
                return

    def _find_tree_node(self, root: TreeNode, data: tuple[str, str] | None) -> TreeNode | None:
        if data is None:
            return None
        if root.data == data:
            return root
        for child in root.subnodes:
            found = self._find_tree_node(child, data)
            if found is not None:
                return found
        return None

    def _on_document_node_selected(self, node: TreeNode) -> None:
        self._selected_node_data = node.data
        self._refresh_selection_label()

    def _refresh_selection_label(self) -> None:
        node_data = self._selected_node_data
        if node_data is None:
            self._selection_label.text = "Selection: <none>"
            return
        self._selection_label.text = f"Selection: {node_data[0]} {self._short_id(node_data[1])}"

    def _last_operation_id(self) -> str:
        component = self._component
        if component is None or not component.document.operations:
            return ""
        return component.document.operations[-1].id

    def _short_id(self, value: str) -> str:
        if len(value) <= 10:
            return value
        return value[:10]

    def _format_vec3(self, value: tuple[float, float, float]) -> str:
        return f"({value[0]:.2f},{value[1]:.2f},{value[2]:.2f})"

    def _request_viewport_update(self) -> None:
        editor = self._editor
        if editor is not None:
            editor.request_viewport_update()

    def _on_viewport_click(
        self,
        entity,
        x: float,
        y: float,
        has_world_point: bool,
        world_x: float,
        world_y: float,
        world_z: float,
        depth: float,
        view_depth: float,
        reproject_screen_error: float,
        reproject_depth_error: float,
        has_mesh_hit: bool,
        mesh_x: float,
        mesh_y: float,
        mesh_z: float,
        normal_x: float,
        normal_y: float,
        normal_z: float,
        triangle_index: int,
        index0: int,
        index1: int,
        index2: int,
    ) -> bool:
        if self._mode == "idle":
            return False

        picked_name = "<none>"
        if entity.valid():
            picked_name = entity.name

        point = self._click_point(
            x,
            y,
            has_mesh_hit,
            mesh_x,
            mesh_y,
            mesh_z,
            has_world_point,
            world_x,
            world_y,
            world_z,
        )
        if point is None:
            log.error("[ProceduralMeshEditor] click ignored: no mesh hit and no OXY plane point")
            return True

        if has_mesh_hit:
            point_kind = "mesh"
        elif has_world_point:
            point_kind = "world"
        else:
            point_kind = "oxy"
        if self._mode == "draw_sketch":
            self._draft_points.append(point)
            self._refresh_mode_label()
            self._request_viewport_update()

        log.info(
            "[ProceduralMeshEditor] viewport click "
            f"mode={self._mode} screen=({x:.1f}, {y:.1f}) picked='{picked_name}' "
            f"{point_kind}=({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f}) "
            f"tri={triangle_index} draft_points={len(self._draft_points)}"
        )
        return True

    def _click_point(
        self,
        x: float,
        y: float,
        has_mesh_hit: bool,
        mesh_x: float,
        mesh_y: float,
        mesh_z: float,
        has_world_point: bool,
        world_x: float,
        world_y: float,
        world_z: float,
    ) -> tuple[float, float, float] | None:
        if has_mesh_hit:
            return (float(mesh_x), float(mesh_y), float(mesh_z))
        if has_world_point:
            return (float(world_x), float(world_y), float(world_z))
        editor = self._editor
        if editor is None:
            return None
        return editor.world_point_on_oxy_plane(x, y)

    def _draw_overlay(self) -> None:
        entity = self._entity
        if entity is None or not entity.valid():
            return
        try:
            pose = entity.transform.global_pose()
            center = pose.lin
        except Exception as e:
            log.error(f"[ProceduralMeshEditor] overlay failed: {e}")
            return

        from termin.visualization.render.immediate import ImmediateRenderer

        renderer = ImmediateRenderer.instance()
        anchor_color = Color4(0.1, 0.9, 1.0, 1.0)
        radius = 0.35
        renderer.line(
            Vec3(center.x - radius, center.y, center.z),
            Vec3(center.x + radius, center.y, center.z),
            anchor_color,
            True,
        )
        renderer.line(
            Vec3(center.x, center.y - radius, center.z),
            Vec3(center.x, center.y + radius, center.z),
            anchor_color,
            True,
        )
        renderer.line(
            Vec3(center.x, center.y, center.z - radius),
            Vec3(center.x, center.y, center.z + radius),
            anchor_color,
            True,
        )
        self._draw_contours(renderer)

    def _draw_contours(self, renderer) -> None:
        contour_color = Color4(0.0, 0.95, 0.95, 1.0)
        draft_color = Color4(1.0, 0.78, 0.12, 1.0)
        point_color = Color4(1.0, 1.0, 1.0, 1.0)
        component = self._component
        if component is not None:
            for item in component.document.items:
                for contour in item.contours:
                    points = item.contour_world_points(contour)
                    self._draw_polyline(renderer, points, contour_color, True)
                    self._draw_points(renderer, points, point_color)
        self._draw_polyline(renderer, self._draft_points, draft_color, False)
        self._draw_points(renderer, self._draft_points, draft_color)

    def _draw_polyline(
        self,
        renderer,
        points: list[tuple[float, float, float]],
        color: Color4,
        closed: bool,
    ) -> None:
        if len(points) < 2:
            return
        for i in range(len(points) - 1):
            renderer.line(self._vec3(points[i]), self._vec3(points[i + 1]), color, False)
        if closed:
            renderer.line(self._vec3(points[-1]), self._vec3(points[0]), color, False)

    def _draw_points(
        self,
        renderer,
        points: list[tuple[float, float, float]],
        color: Color4,
    ) -> None:
        for point in points:
            renderer.sphere_wireframe(self._vec3(point), 0.055, color, 8, False)

    def _vec3(self, point: tuple[float, float, float]) -> Vec3:
        return Vec3(point[0], point[1], point[2])


def register_default_extension() -> None:
    register_component_editor_extension(
        "ProceduralMeshComponent",
        ProceduralMeshEditorExtension,
    )


__all__ = ["ProceduralMeshEditorExtension", "register_default_extension"]
