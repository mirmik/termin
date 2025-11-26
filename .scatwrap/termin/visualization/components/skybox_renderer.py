<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/components/skybox_renderer.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
from typing import Optional<br>
import numpy as np<br>
from ..entity import RenderContext<br>
from ..material import Material<br>
from ..mesh import MeshDrawable<br>
from ..entity import Component<br>
from .mesh_renderer import MeshRenderer<br>
from termin.geombase.pose3 import Pose3<br>
<br>
class SkyboxRenderer(MeshRenderer):<br>
    &quot;&quot;&quot;Specialized renderer for skyboxes (no depth writes and view without translation).&quot;&quot;&quot;<br>
<br>
    def draw(self, context: RenderContext):<br>
        if self.entity is None:<br>
            return<br>
        camera_entity = context.camera.entity if context.camera is not None else None<br>
        if camera_entity is not None:<br>
            #self.entity.transform.local_pose.lin = camera_entity.transform.global_pose().lin.copy()<br>
            self.entity.transform.relocate(Pose3(lin = camera_entity.transform.global_pose().lin))<br>
        original_view = context.view<br>
        view_no_translation = np.array(original_view, copy=True)<br>
        view_no_translation[:3, 3] = 0.0<br>
        context.graphics.set_depth_mask(False)<br>
        context.graphics.set_depth_func(&quot;lequal&quot;)<br>
        self.material.apply(self.entity.model_matrix(), view_no_translation, context.projection, graphics=context.graphics, context_key=context.context_key)<br>
        self.mesh.draw(context)<br>
        context.graphics.set_depth_func(&quot;less&quot;)<br>
        context.graphics.set_depth_mask(True)<br>
<!-- END SCAT CODE -->
</body>
</html>
