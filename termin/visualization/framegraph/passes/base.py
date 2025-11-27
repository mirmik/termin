from __future__ import annotations

from termin.visualization.framegraph.core import FramePass
from termin.visualization.framegraph.context import FrameExecutionContext


class RenderFramePass(FramePass):
    def execute(self, ctx: FrameExecutionContext):
        raise NotImplementedError
