from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.framegraph.passes.present import blit_fbo_to_fbo


@dataclass
class DepthBufferStorage:
    width: int
    height: int
    data: np.ndarray


class FrameDebuggerPass(RenderFramePass):
    """
    Аналог BlitPass, но дополнительно выгружает depth-буфер источника в CPU память.
    """

    def __init__(
        self,
        get_source_res,
        output_res: str = "debug",
        pass_name: str = "FrameDebuggerBlit",
    ):
        super().__init__(
            pass_name=pass_name,
            reads=set(),
            writes={output_res},
        )
        self._get_source_res = get_source_res
        self.output_res = output_res
        self._current_src_name: str | None = None
        self.depth_buffer_storage: DepthBufferStorage | None = None

    def required_resources(self) -> set[str]:
        resources = set(self.writes)
        if self._get_source_res is None:
            self._current_src_name = None
            self.reads = set()
            return resources

        src_name = self._get_source_res()
        if src_name:
            self._current_src_name = src_name
            self.reads = {src_name}
            resources.add(src_name)
        else:
            self.reads = set()
            self._current_src_name = None

        return resources

    def _capture_depth_buffer(self, graphics: "GraphicsBackend", framebuffer) -> None:
        """Читает depth attachment через бэкенд и сохраняет в depth_buffer_storage."""
        self.depth_buffer_storage = None

        depth = graphics.read_depth_buffer(framebuffer)
        if depth is None:
            return

        height, width = depth.shape
        self.depth_buffer_storage = DepthBufferStorage(width=width, height=height, data=depth)

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene=None,
        camera=None,
        context_key: int = 0,
        lights=None,
        canvas=None,
    ):
        px, py, pw, ph = rect
        key = context_key

        if self._get_source_res is None:
            self.depth_buffer_storage = None
            return

        src_name = self._get_source_res()
        if not src_name:
            self.depth_buffer_storage = None
            return

        fb_in = reads_fbos.get(src_name)
        if fb_in is None:
            self.depth_buffer_storage = None
            return

        fb_out = writes_fbos.get(self.output_res)
        if fb_out is None:
            self.depth_buffer_storage = None
            return
        
        blit_fbo_to_fbo(graphics, fb_in, fb_out, (pw, ph), key)
        self._capture_depth_buffer(graphics, fb_in)
