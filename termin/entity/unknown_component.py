"""
UnknownComponent utilities.

UnknownComponent is now implemented in C++ (cpp/termin/entity/unknown_component.cpp).
This module provides the upgrade function for converting UnknownComponents to real
components when their modules are loaded.
"""

from __future__ import annotations


def upgrade_unknown_components(scene) -> int:
    """
    Try to upgrade UnknownComponents to real components.

    Called after a module is loaded to convert placeholders to real components.

    Args:
        scene: Scene to process

    Returns:
        Number of components upgraded
    """
    from tcbase import log
    from termin.entity._entity_native import ComponentRegistry

    if scene is None:
        return 0

    upgraded = 0
    registry = ComponentRegistry.instance()

    for entity in scene.entities:
        # Find all UnknownComponents on this entity (by type name)
        unknown_refs = [
            ref for ref in entity.tc_components
            if ref.type_name == "UnknownComponent"
        ]

        for ref in unknown_refs:
            # Get original_type and original_data via tc_inspect
            original_type = ref.get_field("original_type")
            original_data = ref.get_field("original_data")

            if not original_type:
                continue

            # Check if type is now registered
            if not registry.has(original_type):
                continue

            try:
                # Create real component via registry
                new_ref = entity.add_component_by_name(original_type)
                if not new_ref.valid():
                    continue

                # Deserialize data
                if original_data:
                    new_ref.deserialize_data(original_data, scene.tc_scene_ref)

                # Remove unknown component
                entity.remove_component_ref(ref)
                upgraded += 1

                log.info(f"[UnknownComponent] Upgraded '{original_type}' on entity '{entity.name}'")

            except Exception as e:
                log.error(f"[UnknownComponent] Failed to upgrade '{original_type}': {e}")

    return upgraded
