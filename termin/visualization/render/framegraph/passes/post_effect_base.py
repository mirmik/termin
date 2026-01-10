"""PostEffectPass - Base class for post-processing effect passes.

Provides common functionality for fullscreen shader passes:
- Input/output FBO management
- Inplace rendering support
- Helper methods for drawing fullscreen quads
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Set, Tuple

from termin.visualization.render.framegraph.passes.base import RenderFramePass

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import (
        GraphicsBackend,
        FramebufferHandle,
        GPUTextureHandle,
    )


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
    node_inplace_pairs = [("input_res", "output_res")]

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
        """Post effects are typically inplace (read and write same FBO)."""
        if self.input_res == self.output_res:
            return []
        return [(self.input_res, self.output_res)]

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle | None"],
        writes_fbos: dict[str, "FramebufferHandle | None"],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ) -> None:
        """Execute the post effect pass."""
        if not self.enabled:
            return

        # Get FBOs
        input_fbo = reads_fbos.get(self.input_res)
        output_fbo = writes_fbos.get(self.output_res)

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
            _, _, w, h = rect

        # Bind output FBO
        graphics.bind_framebuffer(output_fbo)
        graphics.set_viewport(0, 0, w, h)

        # Standard post-effect state
        graphics.set_depth_test(False)
        graphics.set_depth_mask(False)
        graphics.set_blend(False)

        # Apply the effect
        self.apply(
            graphics=graphics,
            input_tex=input_tex,
            output_fbo=output_fbo,
            size=(w, h),
            context_key=context_key,
            reads_fbos=reads_fbos,
            scene=scene,
            camera=camera,
        )

        # Restore state
        graphics.set_depth_test(True)
        graphics.set_depth_mask(True)

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
