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
&#9;&quot;&quot;&quot;Responsible for viewport setup, uniforms and draw traversal.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, graphics: GraphicsBackend):<br>
&#9;&#9;self.graphics = graphics<br>
&#9;&#9;self.pick_material = self.create_pick_material()<br>
<br>
&#9;def create_pick_material(self) -&gt; PickMaterial:<br>
&#9;&#9;from termin.visualization.materials.pick_material import PickMaterial<br>
&#9;&#9;return PickMaterial()<br>
<br>
&#9;def render_viewport(self, scene: Scene, camera: CameraComponent, viewport_rect: tuple[int, int, int, int], context_key: int):<br>
&#9;&#9;self.graphics.ensure_ready()<br>
&#9;&#9;x, y, w, h = viewport_rect<br>
&#9;&#9;self.graphics.set_viewport(x, y, w, h)<br>
&#9;&#9;view = camera.get_view_matrix()<br>
&#9;&#9;projection = camera.get_projection_matrix()<br>
&#9;&#9;context = RenderContext(<br>
&#9;&#9;&#9;view=view,<br>
&#9;&#9;&#9;projection=projection,<br>
&#9;&#9;&#9;camera=camera,<br>
&#9;&#9;&#9;scene=scene,<br>
&#9;&#9;&#9;renderer=self,<br>
&#9;&#9;&#9;context_key=context_key,<br>
&#9;&#9;&#9;graphics=self.graphics,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;for entity in scene.entities:<br>
&#9;&#9;&#9;entity.draw(context)<br>
<br>
&#9;def render_viewport_pick(<br>
&#9;&#9;self,<br>
&#9;&#9;scene: Scene,<br>
&#9;&#9;camera: CameraComponent,<br>
&#9;&#9;rect: Tuple[int, int, int, int],<br>
&#9;&#9;context_key: int,<br>
&#9;&#9;pick_ids: dict,<br>
&#9;):<br>
&#9;&#9;x, y, w, h = rect<br>
&#9;&#9;view = camera.view_matrix()<br>
&#9;&#9;proj = camera.projection_matrix()<br>
<br>
&#9;&#9;ctx = RenderContext(<br>
&#9;&#9;&#9;view=view,<br>
&#9;&#9;&#9;projection=proj,<br>
&#9;&#9;&#9;graphics=self.graphics,<br>
&#9;&#9;&#9;context_key=context_key,<br>
&#9;&#9;&#9;scene=scene,<br>
&#9;&#9;&#9;camera=camera,<br>
&#9;&#9;&#9;renderer=self,<br>
&#9;&#9;&#9;phase=&quot;pick&quot;,  # на будущее, но MeshRenderer тут не используем<br>
&#9;&#9;)<br>
<br>
&#9;&#9;gfx = self.graphics<br>
&#9;&#9;# Жёсткое состояние для picking-пасса<br>
&#9;&#9;from termin.visualization.renderpass import RenderState<br>
&#9;&#9;gfx.apply_render_state(RenderState(<br>
&#9;&#9;&#9;depth_test=True,<br>
&#9;&#9;&#9;depth_write=True,<br>
&#9;&#9;&#9;blend=False,<br>
&#9;&#9;&#9;cull=True,<br>
&#9;&#9;))<br>
<br>
&#9;&#9;for ent in scene.entities:<br>
&#9;&#9;&#9;mr = ent.get_component(MeshRenderer)<br>
&#9;&#9;&#9;if mr is None:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;pid = pick_ids.get(ent)<br>
&#9;&#9;&#9;if pid is None:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;color = id_to_rgb(pid)<br>
&#9;&#9;&#9;model = ent.model_matrix()<br>
<br>
&#9;&#9;&#9;self.pick_material.apply_for_pick(<br>
&#9;&#9;&#9;&#9;model=model,<br>
&#9;&#9;&#9;&#9;view=view,<br>
&#9;&#9;&#9;&#9;proj=proj,<br>
&#9;&#9;&#9;&#9;pick_color=color,<br>
&#9;&#9;&#9;&#9;graphics=gfx,<br>
&#9;&#9;&#9;&#9;context_key=context_key,<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;&#9;# берём меш прямо из MeshRenderer, не трогая его passes<br>
&#9;&#9;&#9;if mr.mesh is not None:<br>
&#9;&#9;&#9;&#9;mr.mesh.draw(ctx)<br>
<!-- END SCAT CODE -->
</body>
</html>
