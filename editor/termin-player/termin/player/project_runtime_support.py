"""Shared helpers for project-backed player runtimes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin_assets import AssetTypeRegistry
    from termin.project_modules.runtime import ProjectModulesRuntime

from termin.default_assets.resource_manager import DefaultResourceManager
from termin.player.project_settings import (
    SERVICE_RESOURCE_IGNORE_PATHS,
    ProjectRuntimeSettings,
    load_project_runtime_settings,
)

_RENDER_RESOURCE_TYPE_IDS = frozenset(
    {"glb", "material", "mesh", "pipeline", "shader", "sprite_asset", "texture", "ui"}
)


class ProjectRuntimeSupportError(RuntimeError):
    """A project-backed runtime could not establish its strict runtime contract."""


def register_project_runtime_resources(*, include_render_resources: bool) -> None:
    """Register builtin resources needed before scene deserialization."""
    rm = DefaultResourceManager.instance()
    if not include_render_resources:
        return

    rm.register_builtin_shaders()
    rm.register_builtin_textures()
    rm.register_builtin_materials()
    rm.register_builtin_meshes()
    rm.register_builtin_pipelines()


def load_project_modules(
    project_path: str | Path,
    *,
    log_prefix: str,
    scene_manager=None,
) -> "ProjectModulesRuntime":
    """Load project modules through termin-modules runtime."""
    from termin.base import log
    from termin_modules import ModuleKind, ModuleState
    from termin.project_modules.runtime import get_project_modules_runtime

    runtime = get_project_modules_runtime(scene_manager)
    success = runtime.load_project(Path(project_path))
    if not success:
        detail = runtime.last_error or "project module runtime rejected the load"
        log.error(f"{log_prefix} Module load error: {detail}")

    cpp_loaded = 0
    cpp_failed = 0
    py_loaded = 0
    py_failed = 0

    for record in runtime.records():
        if record.kind == ModuleKind.Cpp:
            if record.state == ModuleState.Loaded:
                cpp_loaded += 1
                log.info(f"{log_prefix} Loaded C++ module: {record.id}")
            elif record.state == ModuleState.Failed:
                cpp_failed += 1
                log.error(f"{log_prefix} Failed to load C++ module {record.id}: {record.error_message}")
        else:
            if record.state == ModuleState.Loaded:
                py_loaded += 1
                log.info(f"{log_prefix} Loaded Python module: {record.id}")
            elif record.state == ModuleState.Failed:
                py_failed += 1
                log.error(f"{log_prefix} Failed to load Python module {record.id}: {record.error_message}")

    log.info(f"{log_prefix} C++ modules: {cpp_loaded} loaded, {cpp_failed} failed")
    log.info(f"{log_prefix} Python modules: {py_loaded} loaded, {py_failed} failed")
    if not success or cpp_failed > 0 or py_failed > 0:
        detail = runtime.last_error or (
            f"{cpp_failed} C++ and {py_failed} Python module(s) failed"
        )
        if not runtime.close():
            cleanup_detail = runtime.last_error or "unknown module cleanup failure"
            log.error(
                f"{log_prefix} Module cleanup after failed startup failed: {cleanup_detail}"
            )
        raise ProjectRuntimeSupportError(f"project module load failed: {detail}")
    return runtime


def create_project_world_controller(project_path: str | Path, *, log_prefix: str):
    """Resolve and create the exact controller selected by canonical project settings."""
    from termin.base import log
    from termin.project import create_selected_world_controller
    from termin.project.settings import load_project_settings

    try:
        settings = load_project_settings(project_path)
        controller = create_selected_world_controller(settings.world_controller)
    except Exception as error:
        log.error(f"{log_prefix} WorldController selection failed: {error}")
        raise ProjectRuntimeSupportError(
            f"failed to create selected WorldController: {error}"
        ) from error

    if settings.world_controller is None:
        log.info(f"{log_prefix} Project has no WorldController selection")
    else:
        log.info(
            f"{log_prefix} Created WorldController "
            f"{settings.world_controller.module}:{settings.world_controller.type_name}"
        )
    return controller


def close_project_modules(
    runtime: "ProjectModulesRuntime | None",
    *,
    log_prefix: str,
) -> bool:
    """Close a project module runtime after all project-owned objects are gone."""
    if runtime is None:
        return True
    if runtime.close():
        return True

    from termin.base import log

    detail = runtime.last_error or "unknown module shutdown failure"
    log.error(f"{log_prefix} Module runtime shutdown failed: {detail}")
    return False


def create_build_import_registry() -> "AssetTypeRegistry":
    from termin_assets import AssetTypeRegistry
    from termin_assets.default_plugins import register_default_import_asset_plugins

    registry = AssetTypeRegistry()
    register_default_import_asset_plugins(registry)
    return registry


def create_asset_import_plugin_map():
    from termin_assets.default_plugins import build_import_plugin_extension_map

    registry = create_build_import_registry()
    return build_import_plugin_extension_map(registry)


def scan_project_assets(
    project_path: str | Path,
    *,
    log_prefix: str,
    include_render_resources: bool = True,
) -> int:
    """Scan project directory for source assets and register them."""
    from termin.base import log

    project_path = Path(project_path)
    rm = DefaultResourceManager.instance()
    ext_map = create_asset_import_plugin_map()
    ignored_roots = _project_asset_ignored_roots(project_path)

    def is_service_ignored(path: str) -> bool:
        resolved = os.path.abspath(path)
        return any(
            resolved == ignored_root or resolved.startswith(ignored_root + os.sep)
            for ignored_root in ignored_roots
        )

    pending = []
    skipped_render_count = 0
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [
            dirname for dirname in dirs
            if not dirname.startswith((".", "__"))
            and not is_service_ignored(os.path.join(root, dirname))
        ]
        for filename in files:
            if filename.startswith("."):
                continue
            path = os.path.join(root, filename)
            if is_service_ignored(path):
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext in ext_map:
                preloader = ext_map[ext]
                if (
                    not include_render_resources
                    and preloader.type_id in _RENDER_RESOURCE_TYPE_IDS
                ):
                    skipped_render_count += 1
                    continue
                pending.append((preloader.priority, path, preloader))

    pending.sort(key=lambda item: (item[0], item[1]))

    loaded_count = 0
    for _priority, path, preloader in pending:
        try:
            result = preloader.preload(path)
            if result is not None:
                log.info(f"{log_prefix} Loading {result.resource_type}: {os.path.basename(path)}")
                rm.register_file(result)
                loaded_count += 1
        except Exception as e:
            log.error(f"{log_prefix} Failed to load {path}: {e}")

    if skipped_render_count:
        log.info(
            f"{log_prefix} Skipped {skipped_render_count} render-only project assets"
        )
    log.info(f"{log_prefix} Loaded {loaded_count} project assets")
    return loaded_count


def _project_asset_ignored_roots(project_path: Path) -> tuple[str, ...]:
    settings = _load_project_settings(project_path)
    ignored_roots = [
        project_path / ignored_path
        for ignored_path in SERVICE_RESOURCE_IGNORE_PATHS
    ]
    ignored_roots.append(project_path / settings.build_output_dir)
    ignored_roots.extend(
        project_path / ignored_path
        for ignored_path in settings.ignored_resource_paths
    )
    return tuple(os.path.abspath(path) for path in ignored_roots)


def _load_project_settings(project_path: Path) -> ProjectRuntimeSettings:
    return load_project_runtime_settings(project_path)
