"""Voxel display shaders with slice clipping."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from tgfx import TcShader


VOXEL_DISPLAY_SHADER_UUID = "termin-engine-voxel-display"
_VOXEL_DISPLAY_SHADER_SOURCE = f"{VOXEL_DISPLAY_SHADER_UUID}.slang"
_BUILTIN_SHADER_CATALOG = "engine-shader-catalog.json"
_LOG = logging.getLogger(__name__)


def _candidate_builtin_shader_roots() -> list[Path]:
    roots: list[Path] = []

    explicit_root = os.environ.get("TERMIN_BUILTIN_SHADER_ROOT")
    if explicit_root:
        roots.append(Path(explicit_root))

    sdk_root = os.environ.get("TERMIN_SDK")
    if sdk_root:
        roots.append(Path(sdk_root) / "share" / "termin" / "builtin_shaders")

    roots.append(Path.cwd() / "share" / "termin" / "builtin_shaders")
    roots.append(Path(sys.prefix) / "share" / "termin" / "builtin_shaders")
    return roots


def _builtin_shader_load_diagnostics() -> str:
    lines = [
        f"TERMIN_SDK={os.environ.get('TERMIN_SDK', '<unset>')}",
        "TERMIN_BUILTIN_SHADER_ROOT="
        f"{os.environ.get('TERMIN_BUILTIN_SHADER_ROOT', '<unset>')}",
        f"cwd={Path.cwd()}",
        f"sys.prefix={sys.prefix}",
        "candidate built-in shader roots:",
    ]
    for root in _candidate_builtin_shader_roots():
        catalog_path = root / _BUILTIN_SHADER_CATALOG
        shader_path = root / _VOXEL_DISPLAY_SHADER_SOURCE
        lines.append(
            "  "
            f"{root} "
            f"(root_exists={root.exists()}, "
            f"catalog_exists={catalog_path.exists()}, "
            f"shader_exists={shader_path.exists()})"
        )
    return "\n".join(lines)


def voxel_display_shader() -> TcShader:
    """Creates shader for voxel display with slice clipping."""
    shader = TcShader.from_builtin_catalog(VOXEL_DISPLAY_SHADER_UUID)
    if not shader.is_valid:
        diagnostics = _builtin_shader_load_diagnostics()
        _LOG.error(
            "Failed to load built-in shader '%s'\n%s",
            VOXEL_DISPLAY_SHADER_UUID,
            diagnostics,
        )
        raise RuntimeError(
            f"Failed to load built-in shader '{VOXEL_DISPLAY_SHADER_UUID}'\n"
            f"{diagnostics}"
        )
    return shader
