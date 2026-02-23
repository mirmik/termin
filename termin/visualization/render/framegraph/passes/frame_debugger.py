"""
FrameDebuggerPass — pass for capturing intermediate framegraph state.

Blits selected resource into FrameGraphCapture's offscreen FBO (no context switch).
"""
from __future__ import annotations

from typing import Set, TYPE_CHECKING, Callable

from termin.visualization.render.framegraph.passes.base import RenderFramePass

if TYPE_CHECKING:
    from tgfx import FramebufferHandle
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class FrameDebuggerPass(RenderFramePass):
    """
    Pass for "between passes" mode in framegraph debugger.

    Blits selected resource into FrameGraphCapture's offscreen FBO.
    No GL context switch — capture happens in the same render context.
    """

    category = "Debug"

    node_inputs = [("input_res", "fbo")]
    node_outputs = []

    def __init__(
        self,
        get_source_res: Callable[[], str | None] | None = None,
        pass_name: str = "FrameDebugger",
    ):
        super().__init__(pass_name=pass_name)
        self._get_source_res = get_source_res
        self._current_src_name: str | None = None

        # FrameGraphCapture from debugger core (set via set_capture)
        self._capture = None

    def set_capture(self, capture) -> None:
        """Set FrameGraphCapture for blit during render."""
        self._capture = capture

    def compute_reads(self) -> Set[str]:
        if self._get_source_res is None:
            return set()
        src_name = self._get_source_res()
        if src_name:
            self._current_src_name = src_name
            return {src_name}
        self._current_src_name = None
        return set()

    def compute_writes(self) -> Set[str]:
        return set()

    def required_resources(self) -> set[str]:
        return set(self.reads)

    def _get_fbo_from_resource(self, resource) -> "FramebufferHandle | None":
        """Extract FramebufferHandle from a framegraph resource."""
        from termin.visualization.render.framegraph.resource import (
            SingleFBO,
            ShadowMapArrayResource,
        )
        from termin.graphics import FramebufferHandle

        if isinstance(resource, ShadowMapArrayResource):
            if len(resource) == 0:
                return None
            return resource[0].fbo

        if isinstance(resource, SingleFBO):
            return resource._fbo

        if isinstance(resource, FramebufferHandle):
            return resource

        return None

    def execute(self, ctx: "ExecuteContext") -> None:
        from tcbase import log

        if self._capture is None:
            log.debug("[FrameDebuggerPass] execute: no capture set")
            return

        if self._get_source_res is None:
            return

        src_name = self._get_source_res()
        if not src_name:
            return

        src_fb = ctx.reads_fbos.get(src_name)
        if src_fb is None:
            log.debug(f"[FrameDebuggerPass] execute: resource '{src_name}' not in reads_fbos. Keys: {list(ctx.reads_fbos.keys())}")
            return

        fbo = self._get_fbo_from_resource(src_fb)
        if fbo is None:
            log.debug(f"[FrameDebuggerPass] execute: could not extract FBO from resource '{src_name}' (type: {type(src_fb).__name__})")
            return

        log.debug(f"[FrameDebuggerPass] execute: capturing '{src_name}', fbo size={fbo.get_size()}")
        # Capture phase: blit into offscreen FBO (same GL context, no switch)
        self._capture.capture_direct(fbo, ctx.graphics)
        log.debug(f"[FrameDebuggerPass] execute: has_capture={self._capture.has_capture()}")
