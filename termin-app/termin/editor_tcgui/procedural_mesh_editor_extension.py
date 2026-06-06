"""tcgui editor extension for ProceduralMeshComponent."""

from __future__ import annotations

from dataclasses import dataclass

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
from termin.csg.document_eval import evaluate_document
from termin.csg.document_tree_model import (
    DocumentTreeNode,
    build_document_tree,
    document_summary,
)
from termin.csg.document_visual_model import build_document_visual_model
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController
from termin.csg.operation_specs import ordered_boolean_operation_specs, ordered_primitive_specs
from termin.csg.procedural_document import ProceduralPlane
from termin.csg.solid_render import (
    PointTransform,
    SolidRenderStyle,
    draw_solid,
)


@dataclass
class _ClickFallback:
    point: tuple[float, float, float] | None = None
    plane: ProceduralPlane | None = None
    kind: str = "fallback"


class ProceduralMeshEditorExtension:
    def __init__(self) -> None:
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._component = None
        self._controller = CsgEditorController()
        self._mode_label = Label()
        self._document_summary_label = Label()
        self._selection_label = Label()
        self._document_tree = TreeWidget()

    def attach(self, editor, entity, component_ref) -> None:
        self._editor = editor
        self._entity = entity
        self._component_ref = component_ref
        self._component = component_ref.to_python()
        if self._component is None:
            log.error("[ProceduralMeshEditor] failed to resolve ProceduralMeshComponent object")
        else:
            self._controller.replace_document(self._component.document)
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
        self._controller = CsgEditorController()
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

        primitive_row = HStack()
        primitive_row.spacing = 4
        primitive_row.preferred_height = px(28)
        for spec in ordered_primitive_specs():
            primitive_row.add_child(
                self._make_command_button(
                    spec.label,
                    lambda k=spec.kind: self._add_primitive_operation(k),
                )
            )
        root.add_child(primitive_row)

        boolean_row = HStack()
        boolean_row.spacing = 4
        boolean_row.preferred_height = px(28)
        for spec in ordered_boolean_operation_specs():
            boolean_row.add_child(
                self._make_command_button(
                    spec.label,
                    lambda k=spec.kind: self._add_boolean_operation(k),
                )
            )
        root.add_child(boolean_row)

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

    def _make_command_button(self, text: str, callback) -> Button:
        btn = Button()
        btn.text = text
        btn.on_click = callback
        return btn

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
        self._mode_label.text = self._mode_text()

    def _close_contour(self) -> None:
        if not self._ensure_controller_document():
            return
        result = self._controller.close_contour()
        if not self._apply_controller_result(result):
            return
        log.info(
            "[ProceduralMeshEditor] contour closed "
            f"contours={self._document_contour_count()}"
        )

    def _add_extrude_operation(self) -> None:
        if not self._ensure_controller_document():
            return
        previous_selection = self._controller.selection
        result = self._controller.extrude_selected()
        if not self._apply_controller_result(result):
            return
        log.info(f"[ProceduralMeshEditor] extrude operation added for selection='{previous_selection}'")

    def _add_primitive_operation(self, kind: str) -> None:
        if not self._ensure_controller_document():
            return
        result = self._controller.add_primitive(kind)
        if not self._apply_controller_result(result):
            return
        log.info(
            "[ProceduralMeshEditor] primitive operation added "
            f"kind='{kind}' selection='{self._controller.selection}'"
        )

    def _add_boolean_operation(self, kind: str) -> None:
        if not self._ensure_controller_document():
            return
        result = self._controller.add_boolean_operation(kind)
        if not self._apply_controller_result(result):
            return
        log.info(
            "[ProceduralMeshEditor] boolean operation added "
            f"kind='{kind}' selection='{self._controller.selection}'"
        )

    def _clear_sketch(self) -> None:
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
        roots = [self._to_tree_node(root) for root in build_document_tree(self._controller.document)]

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

    def _to_tree_node(self, source: DocumentTreeNode) -> TreeNode:
        node = self._tree_node(source.text, (source.kind, source.item_id))
        node.csg_document_node = source
        node.expanded = True
        for child in source.children:
            node.add_node(self._to_tree_node(child))
        return node

    def _restore_tree_selection(self, roots: list[TreeNode]) -> None:
        for root in roots:
            selected = self._find_tree_node(root, self._controller.selection)
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
        self._apply_controller_result(self._controller.select_node(node.data))

    def _refresh_selection_label(self) -> None:
        node_data = self._controller.selection
        if node_data is None:
            self._selection_label.text = "Selection: <none>"
            return
        self._selection_label.text = f"Selection: {node_data[0]} {self._short_id(node_data[1])}"

    def _ensure_controller_document(self) -> bool:
        component = self._component
        if component is None:
            log.error("[ProceduralMeshEditor] component object is not available")
            return False
        if self._controller.document is not component.document:
            self._controller.replace_document(component.document, self._controller.selection)
        return True

    def _apply_controller_result(self, result: CsgEditorCommandResult) -> bool:
        if not result.success:
            if result.message:
                log.error(f"[ProceduralMeshEditor] command failed: {result.message}")
            return False
        component = self._component
        if component is not None and result.document_changed:
            component.document = self._controller.document
        self._refresh_mode_label()
        if result.tree_changed or result.selection_changed:
            self._refresh_document_tree()
        else:
            self._refresh_selection_label()
        if result.preview_changed:
            self._request_viewport_update()
        return True

    def _short_id(self, value: str) -> str:
        if len(value) <= 10:
            return value
        return value[:10]

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
        if self._controller.mode == "idle":
            return False
        if not self._ensure_controller_document():
            return True

        picked_name = "<none>"
        if entity.valid():
            picked_name = entity.name

        local_ray = self._local_ray_from_viewport(x, y)
        fallback = self._click_fallback(
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
        if fallback.point is None:
            log.error("[ProceduralMeshEditor] click ignored: no mesh hit and no OXY plane point")
            return True
        if local_ray is None:
            log.error("[ProceduralMeshEditor] click ignored: viewport ray is not available")
            return True

        ray_origin, ray_direction = local_ray
        result = self._controller.add_draft_point_from_ray(
            ray_origin,
            ray_direction,
            fallback_point=fallback.point,
            fallback_plane=fallback.plane,
            fallback_kind=fallback.kind,
        )
        if not self._apply_controller_result(result):
            return True
        if not self._controller.draft.points:
            log.error("[ProceduralMeshEditor] click ignored: controller did not add a draft point")
            return True
        local_point = self._controller.draft.points[-1]
        world_point = self._world_point_from_local(local_point)
        if world_point is None:
            return True

        if self._controller.mode == "draw_sketch":
            self._refresh_mode_label()
            self._request_viewport_update()

        log.info(
            "[ProceduralMeshEditor] viewport click "
            f"mode={self._controller.mode} screen=({x:.1f}, {y:.1f}) picked='{picked_name}' "
            f"{fallback.kind}_world=({world_point[0]:.3f}, {world_point[1]:.3f}, {world_point[2]:.3f}) "
            f"local=({local_point[0]:.3f}, {local_point[1]:.3f}, {local_point[2]:.3f}) "
            f"tri={triangle_index} draft_points={len(self._controller.draft.points)}"
        )
        return True

    def _local_ray_from_viewport(
        self,
        x: float,
        y: float,
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        editor = self._editor
        entity = self._entity
        if editor is None or entity is None or not entity.valid():
            return None
        world_ray = editor.world_ray_from_viewport_point(x, y)
        if world_ray is None:
            return None
        origin, direction = world_ray
        pose = entity.transform.global_pose()
        local_origin = pose.point_to_local(Vec3(origin[0], origin[1], origin[2]))
        local_direction = pose.vector_to_local(Vec3(direction[0], direction[1], direction[2]))
        return (
            (float(local_origin.x), float(local_origin.y), float(local_origin.z)),
            (float(local_direction.x), float(local_direction.y), float(local_direction.z)),
        )

    def _world_point_from_local(
        self,
        point: tuple[float, float, float],
    ) -> tuple[float, float, float] | None:
        entity = self._entity
        if entity is None or not entity.valid():
            log.error("[ProceduralMeshEditor] cannot convert point to world space: entity is not available")
            return None
        pose = entity.transform.global_pose()
        world = pose.point_to_global(Vec3(point[0], point[1], point[2]))
        return (float(world.x), float(world.y), float(world.z))

    def _click_fallback(
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
    ) -> _ClickFallback:
        if has_mesh_hit:
            local = self._local_point_from_world((float(mesh_x), float(mesh_y), float(mesh_z)))
            return _ClickFallback(local, None, "mesh")
        if has_world_point:
            local = self._local_point_from_world((float(world_x), float(world_y), float(world_z)))
            return _ClickFallback(local, None, "world")
        editor = self._editor
        if editor is None:
            return _ClickFallback()
        world = editor.world_point_on_entity_local_oxy_plane(x, y, self._entity)
        if world is None:
            return _ClickFallback()
        local = self._local_point_from_world(world)
        if local is None:
            return _ClickFallback()
        return _ClickFallback((local[0], local[1], 0.0), ProceduralPlane(), "oxy")

    def _local_point_from_world(
        self,
        point: tuple[float, float, float],
    ) -> tuple[float, float, float] | None:
        entity = self._entity
        if entity is None or not entity.valid():
            log.error("[ProceduralMeshEditor] cannot convert point to local space: entity is not available")
            return None
        pose = entity.transform.global_pose()
        local = pose.point_to_local(Vec3(point[0], point[1], point[2]))
        return (float(local.x), float(local.y), float(local.z))

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
        self._draw_document_debug(renderer, pose)

    def _draw_document_debug(self, renderer, entity_pose) -> None:
        component = self._component
        if component is not None:
            document = self._controller.document
            evaluated_solids = evaluate_document(document)
            for operation in document.operations:
                selected = self._controller.selection == ("operation", operation.id)
                style = self._solid_style(selected)
                for evaluated in evaluated_solids:
                    if evaluated.operation_id == operation.id:
                        draw_solid(
                            renderer,
                            evaluated.solid,
                            style,
                            self._compose_point_transform(entity_pose, evaluated.point_transform),
                        )

            visual_model = build_document_visual_model(
                document,
                self._controller.draft.points,
                self._controller.selection,
            )
            for polyline in visual_model.polylines:
                self._draw_polyline(
                    renderer,
                    entity_pose,
                    polyline.points,
                    self._color4(polyline.color),
                    polyline.closed,
                    polyline.depth_test,
                )
            for point in visual_model.points:
                renderer.sphere_wireframe(
                    self._world_vec3(entity_pose, point.point),
                    point.radius,
                    self._color4(point.color),
                    8,
                    point.depth_test,
                )

    def _compose_point_transform(self, entity_pose, document_transform: PointTransform) -> PointTransform:
        def transform(point: tuple[float, float, float]) -> tuple[float, float, float]:
            local_point = document_transform(point)
            world_point = entity_pose.point_to_global(
                Vec3(local_point[0], local_point[1], local_point[2])
            )
            return (float(world_point.x), float(world_point.y), float(world_point.z))

        return transform

    def _color4(self, color: tuple[float, float, float, float]) -> Color4:
        return Color4(color[0], color[1], color[2], color[3])

    def _solid_style(self, selected: bool) -> SolidRenderStyle:
        if selected:
            return SolidRenderStyle(
                fill_color=Color4(0.15, 0.85, 1.0, 0.32),
                edge_color=Color4(0.85, 1.0, 1.0, 1.0),
                depth_test=True,
            )
        return SolidRenderStyle(
            fill_color=Color4(0.0, 0.65, 0.95, 0.20),
            edge_color=Color4(0.0, 0.95, 0.95, 0.85),
            depth_test=True,
        )

    def _draw_polyline(
        self,
        renderer,
        entity_pose,
        points: list[tuple[float, float, float]],
        color: Color4,
        closed: bool,
        depth_test: bool = False,
    ) -> None:
        if len(points) < 2:
            return
        for i in range(len(points) - 1):
            renderer.line(
                self._world_vec3(entity_pose, points[i]),
                self._world_vec3(entity_pose, points[i + 1]),
                color,
                depth_test,
            )
        if closed:
            renderer.line(
                self._world_vec3(entity_pose, points[-1]),
                self._world_vec3(entity_pose, points[0]),
                color,
                depth_test,
            )

    def _world_vec3(self, entity_pose, point: tuple[float, float, float]) -> Vec3:
        world = entity_pose.point_to_global(Vec3(point[0], point[1], point[2]))
        return Vec3(float(world.x), float(world.y), float(world.z))


def register_default_extension() -> None:
    register_component_editor_extension(
        "ProceduralMeshComponent",
        ProceduralMeshEditorExtension,
    )


__all__ = ["ProceduralMeshEditorExtension", "register_default_extension"]
