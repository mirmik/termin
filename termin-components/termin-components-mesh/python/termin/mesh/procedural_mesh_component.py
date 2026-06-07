"""ProceduralMeshComponent - placeholder document owner for interactive CSG editing."""

from __future__ import annotations

from tcbase import log
from termin.inspect import InspectField
from tmesh import TcMesh

from termin.csg.document_mesh import document_to_mesh3
from termin.csg.procedural_document import ProceduralMeshDocument, ProceduralPlane
from termin.mesh.mesh_component import MeshComponent
from termin.scene.python_component import PythonComponent


def _regenerate_action(component) -> None:
    component.regenerate()


def _document_summary(component) -> str:
    return component.document_summary()


def _get_document_data(component) -> dict:
    return component.document.to_dict()


def _set_document_data(component, data: dict) -> None:
    component.document = ProceduralMeshDocument.from_dict(data)
    component.mark_dirty()


class ProceduralMeshComponent(PythonComponent):
    """Owns a future procedural geometry document and writes MeshComponent later."""

    inspect_fields = {
        "document_name": InspectField(
            path="document_name",
            label="Document Name",
            kind="string",
        ),
        "debug_message": InspectField(
            path="debug_message",
            label="Debug Message",
            kind="string",
        ),
        "auto_regenerate": InspectField(
            path="auto_regenerate",
            label="Auto Regenerate",
            kind="bool",
        ),
        "document_summary": InspectField(
            path=None,
            label="Document",
            kind="string",
            getter=_document_summary,
            read_only=True,
            is_serializable=False,
        ),
        "document": InspectField(
            path=None,
            label="Document Data",
            kind="dict",
            getter=_get_document_data,
            setter=_set_document_data,
            is_inspectable=False,
            is_serializable=True,
        ),
        "regenerate_btn": InspectField(
            path=None,
            label="Regenerate",
            kind="button",
            action=_regenerate_action,
            is_serializable=False,
        ),
    }

    def __init__(
        self,
        document_name: str = "procedural_mesh",
        debug_message: str = "Procedural geometry placeholder",
        auto_regenerate: bool = True,
    ):
        super().__init__(enabled=True)
        self.document_name = document_name
        self.debug_message = debug_message
        self.auto_regenerate = auto_regenerate
        self.document = ProceduralMeshDocument()
        self._dirty = True
        self._last_build_key = None

    def on_added(self) -> None:
        if self.auto_regenerate:
            self.regenerate_if_needed()

    def on_editor_start(self) -> None:
        if self.auto_regenerate:
            self.regenerate_if_needed()

    def start(self) -> None:
        if self.auto_regenerate:
            self.regenerate_if_needed()

    def serialize_data(self) -> dict:
        data = super().serialize_data()
        data["document"] = self.document.to_dict()
        return data

    def deserialize_data(self, data: dict, context=None) -> None:
        if not data:
            return
        clean_data = dict(data)
        document_data = clean_data.pop("document", None)
        super().deserialize_data(clean_data, context)
        if document_data is not None:
            self.document = ProceduralMeshDocument.from_dict(document_data)
        self.mark_dirty()

    def document_summary(self) -> str:
        return (
            f"items={len(self.document.items)}, "
            f"contours={self.document.contour_count()}, "
            f"operations={len(self.document.operations)}, "
            f"dirty={self._dirty}"
        )

    def mark_dirty(self) -> None:
        self._dirty = True

    def add_contour_from_points(
        self,
        points: list[tuple[float, float, float]],
        plane: ProceduralPlane | None = None,
    ) -> bool:
        if plane is None:
            contour = self.document.add_contour_from_points(points)
        else:
            contour = self.document.add_contour_on_plane_from_points(points, plane)
        if contour is None:
            return False
        log.info(
            "[ProceduralMeshComponent] contour added "
            f"id='{contour.id}' points={len(contour.points)} {self.document_summary()}"
        )
        self.mark_dirty()
        if self.auto_regenerate:
            self.regenerate_if_needed()
        return True

    def add_extrude_operation(self, height: float = 1.0) -> bool:
        operation = self.document.add_extrude_operation(height=height)
        if operation is None:
            return False
        log.info(
            "[ProceduralMeshComponent] extrude operation added "
            f"id='{operation.id}' inputs={len(operation.inputs)} height={height:.3f} "
            f"{self.document_summary()}"
        )
        self.mark_dirty()
        if self.auto_regenerate:
            self.regenerate_if_needed()
        return True

    def add_extrude_operation_for_sketch(self, sketch_id: str, height: float = 1.0) -> bool:
        operation = self.document.add_extrude_operation_for_sketch(sketch_id, height=height)
        if operation is None:
            return False
        log.info(
            "[ProceduralMeshComponent] extrude operation added "
            f"id='{operation.id}' sketch='{sketch_id}' inputs={len(operation.inputs)} "
            f"height={height:.3f} {self.document_summary()}"
        )
        self.mark_dirty()
        if self.auto_regenerate:
            self.regenerate_if_needed()
        return True

    def _build_key(self) -> tuple:
        return (self.document_name, self.document.to_dict())

    def regenerate_if_needed(self) -> bool:
        key = self._build_key()
        if not self._dirty and self._last_build_key == key:
            return True
        return self.regenerate()

    def _mesh_component(self):
        ent = self.entity
        if ent is None:
            log.error("[ProceduralMeshComponent] regenerate failed: component has no entity")
            return None
        comp = ent.get_component(MeshComponent)
        if comp is not None:
            return comp
        try:
            ent.add_component_by_name("MeshComponent")
            comp = ent.get_component(MeshComponent)
        except Exception as e:
            log.error(f"[ProceduralMeshComponent] failed to add MeshComponent: {e}")
            return None
        if comp is None:
            log.error("[ProceduralMeshComponent] failed to resolve MeshComponent after add")
            return None
        return comp

    def regenerate(self) -> bool:
        build_key = self._build_key()
        mesh3 = document_to_mesh3(self.document, self.document_name)
        if mesh3 is None:
            log.error(
                "[ProceduralMeshComponent] regenerate failed "
                f"document='{self.document_name}' message='{self.debug_message}'"
            )
            return False

        mesh_component = self._mesh_component()
        if mesh_component is None:
            return False

        tc_mesh = mesh_component.mesh
        if tc_mesh is not None and tc_mesh.is_valid:
            if not tc_mesh.set_from_mesh3(mesh3):
                log.error(
                    "[ProceduralMeshComponent] regenerate failed to update existing mesh "
                    f"document='{self.document_name}' uuid='{tc_mesh.uuid}'"
                )
                return False
        else:
            tc_mesh = TcMesh.from_mesh3(mesh3, self.document_name, "")
            if not tc_mesh.is_valid:
                log.error(f"[ProceduralMeshComponent] failed to create TcMesh name='{self.document_name}'")
                return False
            mesh_component.set_mesh(tc_mesh)
        self._last_build_key = build_key
        self._dirty = False
        log.info(
            "[ProceduralMeshComponent] updated mesh "
            f"document='{self.document_name}' vertices={tc_mesh.vertex_count} triangles={tc_mesh.triangle_count}"
        )
        return True


__all__ = ["ProceduralMeshComponent"]
