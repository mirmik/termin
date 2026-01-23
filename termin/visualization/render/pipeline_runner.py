from __future__ import annotations

from typing import Iterable, Tuple

from termin.visualization.core.viewport import Viewport
from termin.visualization.render.framegraph import FrameGraph, RenderFramePass
from termin.visualization.render.framegraph.execute_context import ExecuteContext
from termin.visualization.platform.backends.base import GraphicsBackend


class PipelineRunner:
    """Executes render pipelines for a collection of viewports."""

    def __init__(self, graphics: GraphicsBackend):
        self.graphics = graphics

    def render_viewports(
        self,
        viewports: Iterable[Viewport],
        framebuffer_size: Tuple[int, int],
        display_fbo,
        context_key: int,
    ) -> None:
        width, height = framebuffer_size

        for viewport in viewports:
            if not viewport.enabled:
                continue

            vx, vy, vw, vh = viewport.rect
            px = int(vx * width)
            py = int(vy * height)
            pw = max(1, int(vw * width))
            ph = max(1, int(vh * height))

            viewport.camera.set_aspect(pw / float(max(1, ph)))

            pipeline = viewport.pipeline
            if pipeline is None:
                continue

            frame_passes = pipeline.passes
            if not frame_passes:
                continue

            for render_pass in frame_passes:
                if isinstance(render_pass, RenderFramePass):
                    render_pass.required_resources()

            graph = FrameGraph(frame_passes)
            schedule = graph.build_schedule()

            alias_groups = graph.fbo_alias_groups()

            fbos = viewport.fbos
            fbos["DISPLAY"] = display_fbo

            for canon, names in alias_groups.items():
                if canon == "DISPLAY":
                    for name in names:
                        fbos[name] = display_fbo
                    continue

                fb = self._get_viewport_fbo(viewport, canon, (pw, ph))
                for name in names:
                    fbos[name] = fb

            for clear_spec in pipeline.clear_specs:
                fb = fbos.get(clear_spec.resource)
                if fb is None:
                    continue
                self.graphics.bind_framebuffer(fb)
                self.graphics.set_viewport(0, 0, pw, ph)
                if clear_spec.color is not None and clear_spec.depth is not None:
                    self.graphics.clear_color_depth(clear_spec.color)
                elif clear_spec.color is not None:
                    self.graphics.clear_color(clear_spec.color)
                elif clear_spec.depth is not None:
                    self.graphics.clear_depth(clear_spec.depth)

            scene = viewport.scene
            lights = scene.build_lights()
            for render_pass in schedule:
                pass_reads = {name: fbos.get(name) for name in render_pass.reads}
                pass_writes = {name: fbos.get(name) for name in render_pass.writes}

                ctx = ExecuteContext(
                    graphics=self.graphics,
                    reads_fbos=pass_reads,
                    writes_fbos=pass_writes,
                    rect=(px, py, pw, ph),
                    scene=scene,
                    camera=viewport.camera,
                    viewport=viewport,
                    context_key=context_key,
                    lights=lights,
                    canvas=viewport.canvas,
                    layer_mask=viewport.effective_layer_mask,
                )
                render_pass.execute(ctx)

    def _get_viewport_fbo(self, viewport: Viewport, key: str, size: Tuple[int, int]):
        framebuffer = viewport.fbos.get(key)
        if framebuffer is None:
            framebuffer = self.graphics.create_framebuffer(size)
            viewport.fbos[key] = framebuffer
        else:
            framebuffer.resize(size)
        return framebuffer
