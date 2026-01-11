"""PostEffectPass - Base class for post-processing effect passes.

Provides common functionality for fullscreen shader passes:
- Input/output FBO management
- Inplace rendering support
- Helper methods for drawing fullscreen quads
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Set, Tuple

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import (
        GraphicsBackend,
        FramebufferHandle,
        GPUTextureHandle,
    )
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class PostEffectPass(RenderFramePass):
    """
    Base class for post-processing effect passes.

    Handles common patterns:
    - Single input texture (color)
    - Single output FBO
    - Inplace rendering (reads input, writes to same FBO)
    - Disabling depth test/blend for fullscreen passes

    Subclasses implement apply() to do the actual effect.
    """

    category = "Effects"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = []

    inspect_fields = {
        "input_res": InspectField(
            path="input_res",
            label="Input",
            kind="string",
        ),
        "output_res": InspectField(
            path="output_res",
            label="Output",
            kind="string",
        ),
    }

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "PostEffect",
    ):
        super().__init__(pass_name)
        self.input_res = input_res
        self.output_res = output_res

    def compute_reads(self) -> Set[str]:
        """Resources this pass reads."""
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        """Resources this pass writes."""
        return {self.output_res}

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """Return inplace aliases only when input and output are the same resource."""
        # When input == output, it's truly inplace (same FBO)
        # When different, they should be separate FBOs (no aliasing)
        return []

    def execute(self, ctx: "ExecuteContext") -> None:
        """Execute the post effect pass."""
        if not self.enabled:
            return

        # Get FBOs
        input_fbo = ctx.reads_fbos.get(self.input_res)
        output_fbo = ctx.writes_fbos.get(self.output_res)

        if input_fbo is None:
            return

        # Get input texture
        input_tex = input_fbo.color_texture()
        if input_tex is None:
            return

        # Get output size
        if output_fbo is not None:
            w, h = output_fbo.get_size()
        else:
            _, _, w, h = ctx.rect

        # Bind output FBO
        ctx.graphics.bind_framebuffer(output_fbo)
        ctx.graphics.set_viewport(0, 0, w, h)

        # Standard post-effect state
        ctx.graphics.set_depth_test(False)
        ctx.graphics.set_depth_mask(False)
        ctx.graphics.set_blend(False)

        # Apply the effect
        self.apply(
            graphics=ctx.graphics,
            input_tex=input_tex,
            output_fbo=output_fbo,
            size=(w, h),
            context_key=ctx.context_key,
            reads_fbos=ctx.reads_fbos,
            scene=ctx.scene,
            camera=ctx.camera,
        )

        # Restore state
        ctx.graphics.set_depth_test(True)
        ctx.graphics.set_depth_mask(True)

    def apply(
        self,
        graphics: "GraphicsBackend",
        input_tex: "GPUTextureHandle",
        output_fbo: "FramebufferHandle | None",
        size: tuple[int, int],
        context_key: int,
        reads_fbos: dict[str, "FramebufferHandle | None"],
        scene,
        camera,
    ) -> None:
        """
        Apply the post effect.

        Override in subclasses to implement the effect.

        Args:
            graphics: Graphics backend.
            input_tex: Input color texture.
            output_fbo: Output FBO (already bound).
            size: (width, height) of the output.
            context_key: Context key for shader caching.
            reads_fbos: All available read FBOs (for extra textures).
            scene: Scene object.
            camera: Camera object.
        """
        raise NotImplementedError("Subclasses must implement apply()")

    def draw_fullscreen_quad(
        self,
        graphics: "GraphicsBackend",
        context_key: int,
    ) -> None:
        """Draw a fullscreen quad using the graphics backend."""
        graphics.draw_ui_textured_quad(context_key)

    def get_texture_from_fbo(
        self,
        reads_fbos: dict[str, "FramebufferHandle | None"],
        resource_name: str,
    ) -> "GPUTextureHandle | None":
        """Get color texture from a resource FBO."""
        fbo = reads_fbos.get(resource_name)
        if fbo is None:
            return None
        return fbo.color_texture()
