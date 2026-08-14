"""NavMesh display shader loaded from the built-in shader catalog."""

from __future__ import annotations

from tcbase import log
from tgfx import TcShader


NAVMESH_DISPLAY_SHADER_UUID = "termin-engine-line-default"


def navmesh_display_shader() -> TcShader:
    """Create the shader used for NavMesh surface and contour display."""
    shader = TcShader.from_builtin_catalog(NAVMESH_DISPLAY_SHADER_UUID)
    if not shader.is_valid:
        log.error(
            "Failed to load built-in NavMesh display shader '%s'",
            NAVMESH_DISPLAY_SHADER_UUID,
        )
        raise RuntimeError(
            f"Failed to load built-in NavMesh display shader "
            f"'{NAVMESH_DISPLAY_SHADER_UUID}'"
        )
    return shader
