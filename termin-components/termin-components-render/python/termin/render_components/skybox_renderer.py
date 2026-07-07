"""Canonical SkyboxRenderer import path."""

from __future__ import annotations

from termin.geombase import Pose3, Vec3
from termin.render_components import MeshRenderer
from termin.render_framework import RenderContext


class SkyboxRenderer(MeshRenderer):
    """Specialized renderer for skyboxes."""

    def draw(self, context: RenderContext):
        if self.entity is None:
            return
        camera_entity = context.camera.entity if context.camera is not None else None
        if camera_entity is not None:
            self.entity.transform.relocate(Pose3(lin=camera_entity.transform.global_pose().lin))
        view_no_translation = context.view.with_translation(Vec3.zero())
        context.graphics.set_depth_mask(False)
        context.graphics.set_depth_func("lequal")
        self.material.apply(self.entity.model_matrix(), view_no_translation, context.projection)

        context.graphics.set_depth_func("less")
        context.graphics.set_depth_mask(True)


__all__ = ["SkyboxRenderer"]
