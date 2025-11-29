from __future__ import annotations
import numpy as np
from termin.geombase.pose3 import Pose3
from termin.visualization.core.entity import Component, RenderContext
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.render.components.mesh_renderer import MeshRenderer

class SkyboxRenderer(MeshRenderer):
    """Specialized renderer for skyboxes (no depth writes and view without translation)."""

    def draw(self, context: RenderContext):
        if self.entity is None:
            return
        camera_entity = context.camera.entity if context.camera is not None else None
        if camera_entity is not None:
            #self.entity.transform.local_pose.lin = camera_entity.transform.global_pose().lin.copy()
            self.entity.transform.relocate(Pose3(lin = camera_entity.transform.global_pose().lin))
        original_view = context.view
        view_no_translation = np.array(original_view, copy=True)
        view_no_translation[:3, 3] = 0.0
        context.graphics.set_depth_mask(False)
        context.graphics.set_depth_func("lequal")
        self.material.apply(self.entity.model_matrix(), view_no_translation, context.projection, graphics=context.graphics, context_key=context.context_key)
        self.mesh.draw(context)
        context.graphics.set_depth_func("less")
        context.graphics.set_depth_mask(True)
