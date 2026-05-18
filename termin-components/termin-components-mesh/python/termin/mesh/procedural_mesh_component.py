"""ProceduralMeshComponent - placeholder document owner for interactive CSG editing."""

from __future__ import annotations

from tcbase import log
from termin.inspect import InspectField
from termin.csg.procedural_document import ProceduralMeshDocument, ProceduralPlane
from termin.scene.python_component import PythonComponent


def _regenerate_action(component) -> None:
    component.regenerate()


def _document_summary(component) -> str:
    return component.document_summary()


def _get_document_data(component) -> dict:
    return component.document.to_dict()


def _set_document_data(component, data: dict) -> None:
    component.document = ProceduralMeshDocument.from_dict(data)


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
    ):
        super().__init__(enabled=True)
        self.document_name = document_name
        self.debug_message = debug_message
        self.document = ProceduralMeshDocument()

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

    def document_summary(self) -> str:
        return (
            f"items={len(self.document.items)}, "
            f"contours={self.document.contour_count()}, "
            f"operations={len(self.document.operations)}"
        )

    def add_contour_from_world_points(
        self,
        points: list[tuple[float, float, float]],
        plane: ProceduralPlane | None = None,
    ) -> bool:
        if plane is None:
            contour = self.document.add_contour_from_world_points(points)
        else:
            contour = self.document.add_contour_on_plane_from_world_points(points, plane)
        if contour is None:
            return False
        log.info(
            "[ProceduralMeshComponent] contour added "
            f"id='{contour.id}' points={len(contour.points)} {self.document_summary()}"
        )
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
        return True

    def regenerate(self) -> None:
        log.info(
            "[ProceduralMeshComponent] regenerate requested "
            f"document='{self.document_name}' message='{self.debug_message}'"
        )


__all__ = ["ProceduralMeshComponent"]
