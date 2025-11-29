from __future__ import annotations

from termin.visualization.render.framegraph.core import FramePass
from termin.visualization.render.framegraph.context import FrameExecutionContext


class RenderFramePass(FramePass):
    def execute(self, ctx: FrameExecutionContext):
        raise NotImplementedError
