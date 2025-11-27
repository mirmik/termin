from __future__ import annotations

from termin.visualization.framegraph.context import FrameContext
from termin.visualization.framegraph.passes.base import RenderFramePass
from termin.visualization.components import MeshRenderer


class IdPass(RenderFramePass):
    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "id",
        pass_name: str = "IdPass",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
            inplace=True,
        )
        self.input_res = input_res
        self.output_res = output_res

    def execute(self, ctx: FrameContext):
        gfx = ctx.graphics
        window = ctx.window
        viewport = ctx.viewport
        scene = viewport.scene
        camera = viewport.camera
        px, py, pw, ph = ctx.rect
        key = ctx.context_key

        fb = ctx.fbos.get(self.output_res)
        gfx.bind_framebuffer(fb)
        gfx.set_viewport(0, 0, pw, ph)
        gfx.clear_color_depth((0.0, 0.0, 0.0, 0.0))

        pick_ids = {}
        for ent in scene.entities:
            if not ent.is_pickable():
                continue

            mr = ent.get_component(MeshRenderer)
            if mr is None:
                continue

            pid = window._get_pick_id_for_entity(ent)
            pick_ids[ent] = pid

        window.renderer.render_viewport_pick(
            scene,
            camera,
            (0, 0, pw, ph),
            key,
            pick_ids,
        )
