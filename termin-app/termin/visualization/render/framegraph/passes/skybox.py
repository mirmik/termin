# SkyBoxPass - re-export from C++.
#
# The legacy Python implementation used ctx.graphics + TcMaterial.apply() via
# the state-machine path. Stage 4 of the tgfx2 migration replaces it with a
# C++ pass that draws through RenderContext2 + bind_material_ubo end-to-end.
from termin._native.render import SkyBoxPass

__all__ = ["SkyBoxPass"]
