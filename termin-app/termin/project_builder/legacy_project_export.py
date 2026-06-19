"""Legacy broad-copy project export path.

This module intentionally preserves the old build.json/assets layout used by
dev/play-mode tooling. Packaged desktop, Android and Quest/OpenXR builds live in
``termin.project_build`` and must not depend on this path.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from termin.project_builder.builder import build_project
from termin.project_builder.manifest import BuildProjectResult


def export_legacy_project(
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path,
    copy_files: bool = True,
    compile_shaders: bool = False,
    compile_asset_shaders: bool = False,
    include_engine_shaders: bool = False,
    shader_usages: Iterable[object] | None = None,
    shader_compiler: str | Path | None = None,
) -> BuildProjectResult:
    return build_project(
        project_root=project_root,
        entry_scene=entry_scene,
        output_dir=output_dir,
        copy_files=copy_files,
        compile_shaders=compile_shaders,
        compile_asset_shaders=compile_asset_shaders,
        include_engine_shaders=include_engine_shaders,
        shader_usages=shader_usages,
        shader_compiler=shader_compiler,
    )
