"""tcgui editor extension for ProceduralMeshComponent."""

from __future__ import annotations

from tcbase import log
from tcbase._geom_native import Vec3
from tgfx._tgfx_native import Color4
from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
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
        self._mode = "idle"
        self._mode_label = Label()

    def attach(self, editor, entity, component_ref) -> None:
        self._editor = editor
        self._entity = entity
        self._component_ref = component_ref
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
        self._mode = "idle"
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
        row.add_child(self._make_button("Move Points", "move_points"))
        root.add_child(row)

        row2 = HStack()
        row2.spacing = 4
        row2.preferred_height = px(28)
        row2.add_child(self._make_button("Extrude", "extrude"))
        row2.add_child(self._make_button("Clear Tool", "idle"))
        root.add_child(row2)

        return root

    def _make_button(self, text: str, mode: str) -> Button:
        btn = Button()
        btn.text = text
        btn.on_click = lambda m=mode: self._set_mode(m)
        return btn

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._mode_label.text = self._mode_text()
        log.info(f"[ProceduralMeshEditor] mode={mode}")

    def _mode_text(self) -> str:
        return f"Mode: {self._mode}"

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

        if has_mesh_hit:
            point = (mesh_x, mesh_y, mesh_z)
            point_kind = "mesh"
        elif has_world_point:
            point = (world_x, world_y, world_z)
            point_kind = "world"
        else:
            log.error("[ProceduralMeshEditor] click ignored: no world point")
            return True

        log.info(
            "[ProceduralMeshEditor] viewport click "
            f"mode={self._mode} screen=({x:.1f}, {y:.1f}) picked='{picked_name}' "
            f"{point_kind}=({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f}) "
            f"tri={triangle_index}"
        )
        return True

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
        color = Color4(0.1, 0.9, 1.0, 1.0)
        radius = 0.35
        renderer.line(
            Vec3(center.x - radius, center.y, center.z),
            Vec3(center.x + radius, center.y, center.z),
            color,
            True,
        )
        renderer.line(
            Vec3(center.x, center.y - radius, center.z),
            Vec3(center.x, center.y + radius, center.z),
            color,
            True,
        )
        renderer.line(
            Vec3(center.x, center.y, center.z - radius),
            Vec3(center.x, center.y, center.z + radius),
            color,
            True,
        )


def register_default_extension() -> None:
    register_component_editor_extension(
        "ProceduralMeshComponent",
        ProceduralMeshEditorExtension,
    )


__all__ = ["ProceduralMeshEditorExtension", "register_default_extension"]
