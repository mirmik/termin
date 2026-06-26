"""Explicit startup bootstrap helpers for Termin programs."""

from collections.abc import Callable

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_bootstrap")

from termin.bootstrap._bootstrap_native import (
    bootstrap_editor,
    bootstrap_player,
    bootstrap_runtime,
    init_inspect_adapters,
    init_pointer_extractors,
    init_python_component_callbacks,
    init_python_inspect_adapters,
    init_python_kind_handlers,
    init_python_render_passes,
    register_runtime_kinds,
    register_scene_extensions,
    shutdown_runtime as _shutdown_runtime_native,
)


def configure_resource_manager_factory(factory: Callable[[], object] | None) -> None:
    """Set the process resource-manager factory during explicit bootstrap."""
    from termin_assets import set_resource_manager_factory

    set_resource_manager_factory(factory)


def _log_shutdown_error(scope: str, exc: Exception) -> None:
    try:
        from tcbase import log

        log.error(f"[Bootstrap] failed to shutdown {scope}: {exc}")
    except Exception:
        pass


def _run_shutdown_step(scope: str, callback: Callable[[], None]) -> None:
    try:
        callback()
    except Exception as exc:
        _log_shutdown_error(scope, exc)


def _shutdown_render_pipelines() -> None:
    from termin.render_framework import shutdown_render_pipelines

    shutdown_render_pipelines()


def _shutdown_python_passes() -> None:
    from termin.render_framework import shutdown_python_passes

    shutdown_python_passes()


def _shutdown_python_components() -> None:
    from termin.scene import shutdown_python_components

    shutdown_python_components()


def _shutdown_glsl_preprocessor() -> None:
    import sys

    if "termin.shader_runtime" in sys.modules:
        from termin.shader_runtime import unregister_glsl_preprocessor_fallback

        unregister_glsl_preprocessor_fallback()
        return

    from termin.materials import unregister_glsl_preprocessor

    unregister_glsl_preprocessor()


def shutdown_runtime() -> None:
    """Release native process-global runtime registries."""
    _shutdown_runtime_native()


def shutdown_player() -> None:
    """Release player/runtime process-global registries and Python callbacks."""
    _run_shutdown_step("render pipelines", _shutdown_render_pipelines)
    _run_shutdown_step("Python render passes", _shutdown_python_passes)
    _run_shutdown_step("Python components", _shutdown_python_components)
    _run_shutdown_step("GLSL preprocessor", _shutdown_glsl_preprocessor)
    _run_shutdown_step("native runtime", shutdown_runtime)


def shutdown_editor() -> None:
    """Release editor/player process-global registries and Python callbacks."""
    shutdown_player()


__all__ = [
    "bootstrap_editor",
    "bootstrap_player",
    "bootstrap_runtime",
    "configure_resource_manager_factory",
    "init_inspect_adapters",
    "init_pointer_extractors",
    "init_python_component_callbacks",
    "init_python_inspect_adapters",
    "init_python_kind_handlers",
    "init_python_render_passes",
    "register_runtime_kinds",
    "register_scene_extensions",
    "shutdown_editor",
    "shutdown_player",
    "shutdown_runtime",
]
