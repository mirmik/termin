from __future__ import annotations
import numpy as np
from termin.geombase import Pose3
from termin.visualization.core.component import Component
from termin.visualization.render.render_context import RenderContext
from termin.visualization.core.material import Material
from termin.visualization.render.components.mesh_renderer import MeshRenderer


class SkyboxRenderer(MeshRenderer):
    """Specialized renderer for skyboxes (no depth writes and view without translation)."""

    def draw(self, context: RenderContext):
        if self.entity is None:
            return
        camera_entity = context.camera.entity if context.camera is not None else None
        if camera_entity is not None:
            self.entity.transform.relocate(Pose3(lin = camera_entity.transform.global_pose().lin))
        original_view = context.view
        view_no_translation = np.array(original_view, copy=True)
        view_no_translation[:3, 3] = 0.0
        context.graphics.set_depth_mask(False)
        context.graphics.set_depth_func("lequal")
        self.material.apply(self.entity.model_matrix(), view_no_translation, context.projection, graphics=context.graphics, context_key=context.context_key)

        # Draw via MeshHandle's gpu
        mesh_data = self._mesh_handle.mesh
        gpu = self._mesh_handle.gpu
        if mesh_data is not None and gpu is not None:
            gpu.draw(context, mesh_data, self._mesh_handle.version)

        context.graphics.set_depth_func("less")
        context.graphics.set_depth_mask(True)
