from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.render.framegraph.core import FramePass

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class RenderFramePass(FramePass):
    def execute(self, ctx: "ExecuteContext") -> None:
        """
        Execute the render pass.

        Args:
            ctx: ExecuteContext containing all render data:
                - graphics: graphics backend
                - reads_fbos/writes_fbos: FBO maps
                - rect: pixel rectangle (px, py, pw, ph)
                - scene, camera: what to render
                - lights: pre-computed lights
                - layer_mask: which entity layers to render
        """
        raise NotImplementedError

    def required_resources(self) -> set[str]:
        """
        Returns set of resources that must be available to this pass.

        By default: union of reads and writes. Subclasses may override
        if dependencies change dynamically.
        """
        return set(self.reads) | set(self.writes)

    def get_resource_specs(self) -> list["ResourceSpec"]:
        """
        Returns list of resource spec requirements.

        Subclasses may override to declare:
        - Fixed resource size (e.g., shadow map 1024x1024)
        - Clear parameters (color, depth)
        - Attachment format

        Returns empty list by default (no special requirements).
        """
        return []

    def destroy(self) -> None:
        """
        Clean up pass resources.

        Override in subclasses to release FBOs, textures, etc.
        """
        pass

    def _blit_to_debugger(
        self, graphics: "GraphicsBackend", src_fbo: "FramebufferHandle"
    ) -> None:
        """
        Blit current FBO state into debugger's capture FBO.

        Used for "inside pass" mode — capturing intermediate state
        after rendering a specific entity.
        """
        cap = self._tc_pass.get_debug_capture()
        if cap is None:
            return
        cap.capture_direct(src_fbo, graphics)
