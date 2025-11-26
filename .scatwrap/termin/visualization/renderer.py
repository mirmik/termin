<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/renderer.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Renderer configures graphics state and draws entities.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from .camera import CameraComponent, PerspectiveCameraComponent<br>
from .scene import Scene<br>
from .entity import RenderContext<br>
from .backends.base import GraphicsBackend<br>
from .components import MeshRenderer<br>
from .picking import id_to_rgb<br>
<br>
<br>
class Renderer:<br>
    &quot;&quot;&quot;Responsible for viewport setup, uniforms and draw traversal.&quot;&quot;&quot;<br>
<br>
    def __init__(self, graphics: GraphicsBackend):<br>
        self.graphics = graphics<br>
        self.pick_material = self.create_pick_material()<br>
<br>
    def create_pick_material(self) -&gt; PickMaterial:<br>
        from termin.visualization.materials.pick_material import PickMaterial<br>
        return PickMaterial()<br>
<br>
    def render_viewport(self, scene: Scene, camera: CameraComponent, viewport_rect: tuple[int, int, int, int], context_key: int):<br>
        self.graphics.ensure_ready()<br>
        x, y, w, h = viewport_rect<br>
        self.graphics.set_viewport(x, y, w, h)<br>
        view = camera.get_view_matrix()<br>
        projection = camera.get_projection_matrix()<br>
        context = RenderContext(<br>
            view=view,<br>
            projection=projection,<br>
            camera=camera,<br>
            scene=scene,<br>
            renderer=self,<br>
            context_key=context_key,<br>
            graphics=self.graphics,<br>
        )<br>
<br>
        for entity in scene.entities:<br>
            entity.draw(context)<br>
<br>
    def render_viewport_pick(<br>
        self,<br>
        scene: Scene,<br>
        camera: CameraComponent,<br>
        rect: Tuple[int, int, int, int],<br>
        context_key: int,<br>
        pick_ids: dict,<br>
    ):<br>
        x, y, w, h = rect<br>
        view = camera.view_matrix()<br>
        proj = camera.projection_matrix()<br>
<br>
        ctx = RenderContext(<br>
            view=view,<br>
            projection=proj,<br>
            graphics=self.graphics,<br>
            context_key=context_key,<br>
            scene=scene,<br>
            camera=camera,<br>
            renderer=self,<br>
            phase=&quot;pick&quot;,  # на будущее, но MeshRenderer тут не используем<br>
        )<br>
<br>
        gfx = self.graphics<br>
        # Жёсткое состояние для picking-пасса<br>
        from termin.visualization.renderpass import RenderState<br>
        gfx.apply_render_state(RenderState(<br>
            depth_test=True,<br>
            depth_write=True,<br>
            blend=False,<br>
            cull=True,<br>
        ))<br>
<br>
        for ent in scene.entities:<br>
            mr = ent.get_component(MeshRenderer)<br>
            if mr is None:<br>
                continue<br>
<br>
            pid = pick_ids.get(ent)<br>
            if pid is None:<br>
                continue<br>
<br>
            color = id_to_rgb(pid)<br>
            model = ent.model_matrix()<br>
<br>
            self.pick_material.apply_for_pick(<br>
                model=model,<br>
                view=view,<br>
                proj=proj,<br>
                pick_color=color,<br>
                graphics=gfx,<br>
                context_key=context_key,<br>
            )<br>
<br>
            # берём меш прямо из MeshRenderer, не трогая его passes<br>
            if mr.mesh is not None:<br>
                mr.mesh.draw(ctx)<br>
<!-- END SCAT CODE -->
</body>
</html>
