"""Default tcgui component editor extension registrations."""

from __future__ import annotations

from tcbase import log


def register_default_component_editor_extensions() -> None:
    try:
        from termin.editor_tcgui.procedural_mesh_editor_extension import (
            register_default_extension as register_procedural_mesh_extension,
        )

        register_procedural_mesh_extension()
    except Exception as e:
        log.error(f"[ComponentEditorExtension] procedural mesh registration failed: {e}")

    try:
        from termin.editor_tcgui.foliage_layer_editor_extension import (
            register_default_extension as register_foliage_layer_extension,
        )

        register_foliage_layer_extension()
    except Exception as e:
        log.error(f"[ComponentEditorExtension] foliage layer registration failed: {e}")


__all__ = ["register_default_component_editor_extensions"]
