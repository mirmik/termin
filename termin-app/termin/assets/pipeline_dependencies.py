"""Compatibility re-export for pipeline dependency helpers.

Canonical module: :mod:`termin.render.pipeline_dependencies`.
"""

from termin.render.pipeline_dependencies import (
    material_pass_materials,
    refresh_loaded_materials_for_shader,
    reload_pipelines_for_material_dependencies,
    uses_material_names,
)

__all__ = [
    "material_pass_materials",
    "refresh_loaded_materials_for_shader",
    "reload_pipelines_for_material_dependencies",
    "uses_material_names",
]
