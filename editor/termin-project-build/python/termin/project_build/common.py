"""Shared helpers for project build wrappers."""

from __future__ import annotations

import json
import os
import gc
from pathlib import Path


def find_project_or_standard_shader(project_root: Path, shader_name: str) -> Path:
    """Resolve project-deployed stdlib overrides before the SDK fallback."""
    matches = sorted(
        path
        for path in project_root.rglob(f"{shader_name}.shader")
        if not any(
            part in {".git", "__pycache__", "build", "dist"}
            for part in path.relative_to(project_root).parts
        )
    )
    if matches:
        return matches[0]

    from termin.stdlib import stdlib_root

    standard_path = stdlib_root() / "shaders" / f"{shader_name}.shader"
    if standard_path.is_file():
        return standard_path
    raise FileNotFoundError(f"shader asset '{shader_name}' was not found")


def initialize_project_build_runtime_state(log_prefix: str) -> None:
    """Initialize process runtime registries required while loading build assets."""
    try:
        from termin.bootstrap import bootstrap_runtime

        bootstrap_runtime()
    except Exception:
        from termin.base import log

        log.error(
            f"{log_prefix} Failed to initialize project build runtime state",
            exc_info=True,
        )
        raise


def initialize_project_build_player_runtime_state(log_prefix: str) -> None:
    """Initialize the Python-enabled registry contract used by desktop player bundles."""
    try:
        from termin.bootstrap import bootstrap_player

        bootstrap_player()
    except Exception:
        from termin.base import log

        log.error(
            f"{log_prefix} Failed to initialize desktop player build runtime state",
            exc_info=True,
        )
        raise


def preload_project_resources(project_root: Path, log_prefix: str) -> None:
    """Load project resources into runtime registries for non-editor builds."""
    try:
        from termin.default_assets.default_preloaders import create_default_preloaders
        from termin.default_assets.resource_manager import DefaultResourceManager

        resource_manager = DefaultResourceManager.instance()
        processors = create_default_preloaders(resource_manager)
        by_extension = {
            extension: processor
            for processor in processors
            for extension in processor.extensions
        }
        pending: list[tuple[int, str]] = []
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [
                directory
                for directory in dirs
                if not directory.startswith((".", "__"))
                and directory not in {"build", "dist"}
            ]
            for filename in files:
                if filename.startswith("."):
                    continue
                path = Path(root) / filename
                extension = path.suffix.lower()
                processor = by_extension.get(extension)
                if processor is not None:
                    pending.append((processor.priority, str(path)))

        _register_standard_shaders_for_project_materials(
            resource_manager,
            project_root,
            [Path(path) for _priority, path in pending if Path(path).suffix == ".material"],
            log_prefix,
        )
        for _priority, path in sorted(pending, key=lambda item: (item[0], item[1])):
            by_extension[Path(path).suffix.lower()].on_file_added(path)
    except Exception:
        from termin.base import log
        log.error(f"{log_prefix} Failed to preload project resources", exc_info=True)


def _register_standard_shaders_for_project_materials(
    resource_manager,
    project_root: Path,
    material_paths: list[Path],
    log_prefix: str,
) -> None:
    """Make stdlib shader assets available before material preloaders run."""
    from termin.base import log
    from termin.default_assets.render.shader_asset import ShaderAsset
    for material_path in material_paths:
        try:
            document = json.loads(material_path.read_text(encoding="utf-8"))
            shader_name = document.get("shader") if isinstance(document, dict) else None
            if not isinstance(shader_name, str) or not shader_name:
                continue
            if resource_manager.get_shader_asset(shader_name) is not None:
                continue

            shader_path = find_project_or_standard_shader(
                project_root,
                shader_name,
            )
            shader_asset = ShaderAsset.from_file(shader_path, name=shader_name)
            resource_manager.register_shader_asset(
                shader_name,
                shader_asset,
                source_path=str(shader_path),
                uuid=shader_asset.uuid,
            )
        except Exception:
            log.error(
                f"{log_prefix} Failed to prepare shader dependency for "
                f"project material '{material_path}'",
                exc_info=True,
            )


def cleanup_project_build_runtime_state(log_prefix: str) -> None:
    """Release process-wide resource state created during project build."""
    try:
        from termin.default_assets.resource_manager import DefaultResourceManager

        DefaultResourceManager.shutdown_instance()
        gc.collect()
    except Exception:
        from termin.base import log

        log.error(f"{log_prefix} Failed to clean project build runtime state", exc_info=True)


def read_project_name(project_root: Path) -> str:
    project_files = sorted(project_root.glob("*.terminproj"))
    if not project_files:
        return project_root.name

    project_file = project_files[0]
    try:
        with open(project_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return project_file.stem

    if not isinstance(data, dict):
        return project_file.stem

    name = data.get("name")
    if isinstance(name, str) and name != "":
        return name
    return project_file.stem
