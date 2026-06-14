# SkyBoxPass - re-export from C++.
#
# The legacy Python implementation used ctx.graphics + TcMaterial.apply() via
# the state-machine path. Stage 4 of the tgfx2 migration replaces it with a
# C++ pass that draws through RenderContext2 and reflected material resources.
from termin.render_passes import SkyBoxPass

__all__ = ["SkyBoxPass"]
