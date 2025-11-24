"""Renderer configures graphics state and draws entities."""

from __future__ import annotations

from .camera import CameraComponent, PerspectiveCameraComponent
from .scene import Scene
from .entity import RenderContext
from .backends.base import GraphicsBackend
from .components import MeshRenderer
from .picking import id_to_rgb


class Renderer:
    """Responsible for viewport setup, uniforms and draw traversal."""

    def __init__(self, graphics: GraphicsBackend):
        self.graphics = graphics
        self.pick_material = self.create_pick_material()

    def create_pick_material(self) -> PickMaterial:
        from termin.visualization.materials.pick_material import PickMaterial
        return PickMaterial()

    def render_viewport(self, scene: Scene, camera: CameraComponent, viewport_rect: tuple[int, int, int, int], context_key: int):
        self.graphics.ensure_ready()
        x, y, w, h = viewport_rect
        self.graphics.set_viewport(x, y, w, h)
        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()
        context = RenderContext(
            view=view,
            projection=projection,
            camera=camera,
            scene=scene,
            renderer=self,
            context_key=context_key,
            graphics=self.graphics,
        )

        for entity in scene.entities:
            entity.draw(context)

    def render_viewport_pick(
        self,
        scene: Scene,
        camera: CameraComponent,
        rect: Tuple[int, int, int, int],
        context_key: int,
        pick_ids: dict,
    ):
        x, y, w, h = rect
        view = camera.view_matrix()
        proj = camera.projection_matrix()

        ctx = RenderContext(
            view=view,
            projection=proj,
            graphics=self.graphics,
            context_key=context_key,
            scene=scene,
            camera=camera,
            renderer=self,
            phase="pick",  # на будущее, но MeshRenderer тут не используем
        )

        gfx = self.graphics
        # Жёсткое состояние для picking-пасса
        from termin.visualization.renderpass import RenderState
        gfx.apply_render_state(RenderState(
            depth_test=True,
            depth_write=True,
            blend=False,
            cull=True,
        ))

        for ent in scene.entities:
            mr = ent.get_component(MeshRenderer)
            if mr is None:
                continue

            pid = pick_ids.get(ent)
            if pid is None:
                continue

            color = id_to_rgb(pid)
            model = ent.model_matrix()

            print("Pick color of entity:", color)  # --- DEBUG ---
            self.pick_material.apply_for_pick(
                model=model,
                view=view,
                proj=proj,
                pick_color=color,
                graphics=gfx,
                context_key=context_key,
            )

            # берём меш прямо из MeshRenderer, не трогая его passes
            mr.mesh.draw(ctx)