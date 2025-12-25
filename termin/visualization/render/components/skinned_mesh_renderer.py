"""SkinnedMeshRenderer - Renderer component for skinned meshes with skeletal animation.

Re-exports C++ SkinnedMeshRenderer with additional Python-only helpers.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from termin._native.render import SkinnedMeshRenderer as CppSkinnedMeshRenderer
from termin.visualization.render.drawable import GeometryDrawCall

if TYPE_CHECKING:
    from termin.visualization.render.render_context import RenderContext


class SkinnedMeshRenderer(CppSkinnedMeshRenderer):
    """
    Renderer component for skinned meshes with skeletal animation.

    Extends C++ SkinnedMeshRenderer with Python-specific helpers.
    """

    def on_editor_start(self):
        """Called when scene starts in editor mode. Refresh bone matrices from skeleton."""
        si = self.skeleton_instance
        if si is not None:
            si.update()

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """
        Returns GeometryDrawCalls with skinned material variant.
        """
        mat = self.get_skinned_material()
        if mat is None:
            return []

        if phase_mark is None:
            phases = list(mat.phases)
        else:
            phases = [p for p in mat.phases if p.phase_mark == phase_mark]

        phases.sort(key=lambda p: p.priority)
        return [GeometryDrawCall(phase=p) for p in phases]

    def serialize_data(self) -> dict:
        """Serialize SkinnedMeshRenderer."""
        # Use MeshRenderer serialization
        from termin._native.render import MeshRenderer
        data = MeshRenderer.serialize_data(self) if hasattr(MeshRenderer, 'serialize_data') else {}
        # Add mesh and material handles if not present
        if 'mesh' not in data and self.mesh.is_valid:
            data['mesh'] = self.mesh.serialize()
        if 'material' not in data and self.material.is_valid:
            data['material'] = self.material.serialize()
        data['cast_shadow'] = self.cast_shadow
        return data


# Re-export for backward compatibility
__all__ = ["SkinnedMeshRenderer"]
