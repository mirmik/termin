"""Voxel display shaders with slice clipping."""

from __future__ import annotations

from tgfx import TcShader


VOXEL_DISPLAY_SHADER_UUID = "termin-engine-voxel-display"


def voxel_display_shader() -> TcShader:
    """Creates shader for voxel display with slice clipping."""
    shader = TcShader.from_builtin_catalog(VOXEL_DISPLAY_SHADER_UUID)
    if not shader.is_valid:
        raise RuntimeError(f"Failed to load built-in shader '{VOXEL_DISPLAY_SHADER_UUID}'")
    return shader
