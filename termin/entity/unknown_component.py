"""
UnknownComponent - placeholder for components whose type is not registered.

When a scene is loaded and a component type is not found (e.g., module not loaded
or has errors), an UnknownComponent is created to preserve the data. When the
module is loaded/fixed, the component can be upgraded to the real type.
"""

from __future__ import annotations

from typing import Any, Dict

from termin.visualization.core.python_component import PythonComponent
from termin.editor.inspect_field import InspectField


class UnknownComponent(PythonComponent):
    """
    Placeholder component for unknown/unloaded component types.

    Preserves original type name and serialized data so that:
    1. The component can be upgraded when the module is loaded
    2. If the scene is saved, the original data is preserved
    """

    inspect_fields: Dict[str, Any] = {
        "original_type": InspectField(
            label="Original Type",
            kind="string",
            read_only=True,
        ),
    }

    original_type: str = ""
    original_data: dict = None

    def __init__(self, original_type: str = "", original_data: dict = None):
        super().__init__(enabled=False)  # Disabled by default since it's a placeholder
        self.original_type = original_type
        self.original_data = original_data if original_data is not None else {}

    @classmethod
    def type_name(cls) -> str:
        return "UnknownComponent"

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize as the original component type.

        This ensures that if the scene is saved while the component is unavailable,
        it will be correctly restored when the module is loaded.
        """
        return {
            "type": self.original_type,
            "data": self.original_data,
        }

    def serialize_data(self) -> Dict[str, Any]:
        """Return original data for serialization."""
        return self.original_data

    def deserialize_data(self, data: Dict[str, Any], context: Any = None) -> None:
        """
        Deserialize - store the data for later upgrade.

        Note: original_type should be set before calling this.
        """
        self.original_data = data if data else {}


# Register the component
from termin.entity._entity_native import ComponentRegistry
ComponentRegistry.instance().register_python("UnknownComponent", UnknownComponent)


def upgrade_unknown_components(scene) -> int:
    """
    Try to upgrade UnknownComponents to real components.

    Called after a module is loaded to convert placeholders to real components.

    Args:
        scene: Scene to process

    Returns:
        Number of components upgraded
    """
    from termin._native import log
    from termin.entity._entity_native import ComponentRegistry

    if scene is None:
        return 0

    upgraded = 0
    registry = ComponentRegistry.instance()

    for entity in scene.entities:
        # Find all UnknownComponents on this entity
        unknown_components = [
            c for c in entity.components
            if isinstance(c, UnknownComponent)
        ]

        for unknown in unknown_components:
            original_type = unknown.original_type
            original_data = unknown.original_data

            # Check if type is now registered
            if not registry.has(original_type):
                continue

            try:
                # Create real component via registry
                comp = registry.create(original_type)
                if comp is None:
                    continue

                # Deserialize data - all components have this method
                comp.deserialize_data(original_data, None)

                # Remove unknown, add real
                entity.remove_component(unknown)
                entity.add_component(comp)
                upgraded += 1

                log.info(f"[UnknownComponent] Upgraded '{original_type}' on entity '{entity.name}'")

            except Exception as e:
                log.error(f"[UnknownComponent] Failed to upgrade '{original_type}': {e}")

    return upgraded
