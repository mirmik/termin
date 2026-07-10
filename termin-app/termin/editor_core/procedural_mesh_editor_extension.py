"""Toolkit-neutral state and commands for the ProceduralMesh editor extension."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tcbase import log

from termin.csg.document_tree_model import document_summary
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController


@dataclass(frozen=True)
class ProceduralMeshExtensionSnapshot:
    mode: str
    draft_point_count: int
    document_summary: str
    selection: tuple[str, str] | None
    status: str


class ProceduralMeshExtensionModel:
    """Own CSG document mutation independently from frontend widgets."""

    def __init__(self) -> None:
        from termin.editor_core.procedural_mesh_viewport_interaction import (
            ProceduralMeshViewportInteraction,
        )

        self.controller = CsgEditorController()
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._component = None
        self._status = "Ready"
        self._changed_handler: Callable[[ProceduralMeshExtensionSnapshot], None] | None = None
        self.viewport_interaction = ProceduralMeshViewportInteraction(self)

    @property
    def component(self):
        return self._component

    @property
    def snapshot(self) -> ProceduralMeshExtensionSnapshot:
        return ProceduralMeshExtensionSnapshot(
            mode=self.controller.mode,
            draft_point_count=len(self.controller.draft.points),
            document_summary=document_summary(self.controller.document),
            selection=self.controller.selection,
            status=self._status,
        )

    def set_changed_handler(
        self,
        handler: Callable[[ProceduralMeshExtensionSnapshot], None] | None,
    ) -> None:
        self._changed_handler = handler
        if handler is not None:
            handler(self.snapshot)

    def attach(self, editor, entity, component_ref) -> None:
        self._editor = editor
        self._entity = entity
        self._component_ref = component_ref
        self._component = component_ref.to_python()
        if self._component is None:
            log.error("[ProceduralMeshEditor] failed to resolve ProceduralMeshComponent object")
        else:
            self.controller.replace_document(self._component.document)
        self._status = "Ready"
        self.viewport_interaction.attach(editor, entity)
        self._notify_changed()

    def detach(self) -> None:
        self.viewport_interaction.detach()
        self._changed_handler = None
        self._editor = None
        self._entity = None
        self._component_ref = None
        self._component = None
        self.controller = CsgEditorController()
        self._status = "Ready"

    def set_status(self, status: str) -> None:
        self._status = status
        self._notify_changed()

    def apply_result(
        self,
        result: CsgEditorCommandResult,
        default_status: str = "",
    ) -> bool:
        if not result.success:
            if result.message:
                self._status = result.message
                log.error(f"[ProceduralMeshEditor] command failed: {result.message}")
                self._notify_changed()
            return False
        component = self._component
        if component is not None and result.document_changed:
            component.document = self.controller.document
            component.mark_dirty()
            if component.auto_regenerate:
                component.regenerate_if_needed()
        status = result.message if result.message else default_status
        if status:
            self._status = status
        self._notify_changed()
        if result.preview_changed:
            self._request_viewport_update()
        return True

    def select_node(self, selection: tuple[str, str] | None) -> bool:
        return self.apply_result(self.controller.select_node(selection))

    def start_draw_sketch(self) -> bool:
        return self.apply_result(self.controller.start_draw_sketch())

    def close_contour(self) -> bool:
        return self.apply_result(self.controller.close_contour())

    def finish_wall_path(self) -> bool:
        return self.apply_result(self.controller.finish_wall_path())

    def clear_tool(self) -> bool:
        return self.apply_result(self.controller.cancel_current_tool())

    def clear_document(self) -> bool:
        return self.apply_result(self.controller.new_document(), "Cleared")

    def add_primitive(self, kind: str) -> bool:
        return self.apply_result(self.controller.add_primitive(kind), f"{kind.title()} added")

    def add_boolean_operation(self, kind: str) -> bool:
        return self.apply_result(self.controller.add_boolean_operation(kind))

    def extrude_selected(self) -> bool:
        return self.apply_result(self.controller.extrude_selected())

    def wall_selected(self) -> bool:
        return self.apply_result(self.controller.wall_selected())

    def set_primitive_params(self, operation_id: str, params: dict) -> bool:
        return self.apply_result(
            self.controller.set_primitive_params(operation_id, params),
            "Parameters updated",
        )

    def set_extrude_vector(
        self,
        operation_id: str,
        vector: tuple[float, float, float],
    ) -> bool:
        return self.apply_result(
            self.controller.set_extrude_vector(operation_id, vector),
            "Extrude vector updated",
        )

    def set_operation_transform(
        self,
        operation_id: str,
        center: tuple[float, float, float],
        rotation: tuple[float, float, float],
    ) -> bool:
        return self.apply_result(
            self.controller.set_operation_transform(operation_id, center, rotation),
            "Transform updated",
        )

    def set_wall_params(
        self,
        operation_id: str,
        height: float,
        thickness: float,
        alignment: str,
    ) -> bool:
        return self.apply_result(
            self.controller.set_wall_params(operation_id, height, thickness, alignment),
            "Wall parameters updated",
        )

    def set_wall_corner_offset(
        self,
        operation_id: str,
        source_id: str,
        point_index: int,
        offset: float,
    ) -> bool:
        return self.apply_result(
            self.controller.set_wall_corner_offset(
                operation_id,
                source_id,
                point_index,
                offset,
            ),
            "Wall corner updated",
        )

    def set_sketch_plane(self, sketch_id: str, plane) -> bool:
        return self.apply_result(
            self.controller.set_sketch_plane(sketch_id, plane),
            "Sketch plane updated",
        )

    def set_contour_point(
        self,
        contour_id: str,
        point_index: int,
        point: tuple[float, float],
    ) -> bool:
        return self.apply_result(
            self.controller.set_contour_point(contour_id, point_index, point),
            "Contour point updated",
        )

    def set_path_point(
        self,
        path_id: str,
        point_index: int,
        point: tuple[float, float],
    ) -> bool:
        return self.apply_result(
            self.controller.set_path_point(path_id, point_index, point),
            "Path point updated",
        )

    def start_add_outer_contour(self) -> bool:
        return self.apply_result(self.controller.start_add_outer_contour())

    def start_add_hole_contour(self) -> bool:
        return self.apply_result(self.controller.start_add_hole_contour())

    def start_add_wall_path(self) -> bool:
        return self.apply_result(self.controller.start_add_wall_path())

    def ensure_component_document(self) -> bool:
        component = self._component
        if component is None:
            log.error("[ProceduralMeshEditor] component object is not available")
            return False
        if self.controller.document is not component.document:
            self.controller.replace_document(component.document, self.controller.selection)
            self._notify_changed()
        return True

    def _request_viewport_update(self) -> None:
        editor = self._editor
        if editor is not None:
            editor.request_viewport_update()

    def _notify_changed(self) -> None:
        handler = self._changed_handler
        if handler is not None:
            handler(self.snapshot)


__all__ = [
    "ProceduralMeshExtensionModel",
    "ProceduralMeshExtensionSnapshot",
]
