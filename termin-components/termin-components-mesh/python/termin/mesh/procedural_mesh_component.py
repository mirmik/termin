"""ProceduralMeshComponent - placeholder document owner for interactive CSG editing."""

from __future__ import annotations

from tcbase import log
from termin.inspect import InspectField
from termin.scene.python_component import PythonComponent


def _regenerate_action(component) -> None:
    component.regenerate()


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

    def regenerate(self) -> None:
        log.info(
            "[ProceduralMeshComponent] regenerate requested "
            f"document='{self.document_name}' message='{self.debug_message}'"
        )


__all__ = ["ProceduralMeshComponent"]
