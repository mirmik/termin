"""Explicit startup bootstrap helpers for Termin programs."""

from collections.abc import Callable

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_bootstrap")

from termin.bootstrap._bootstrap_native import (
    bootstrap_editor as _bootstrap_editor_native,
    bootstrap_player as _bootstrap_player_native,
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


def _publish_builtin_type_projections() -> None:
    import importlib

    from termin.default_assets.builtin_types import (
        get_default_builtin_component_specs,
        get_default_builtin_frame_pass_specs,
    )
    from termin.render_framework import (
        tc_pass_registry_bind_class_projection,
        tc_pass_registry_has,
    )
    from termin.scene import ComponentRegistry, PythonComponent, publish_python_components

    component_classes: list[tuple[str, type]] = []
    python_components: list[type[PythonComponent]] = []
    for module_name, class_name in get_default_builtin_component_specs():
        module = importlib.import_module(module_name)
        cls = module.__dict__.get(class_name)
        if not isinstance(cls, type):
            raise RuntimeError(
                f"builtin component provider {module_name} does not expose class {class_name}"
            )
        component_classes.append((class_name, cls))
        if issubclass(cls, PythonComponent):
            python_components.append(cls)

    publish_python_components(python_components, owner="termin-builtin-python")
    component_registry = ComponentRegistry.instance()
    for class_name, cls in component_classes:
        if not component_registry.bind_class_projection(class_name, cls):
            raise RuntimeError(
                f"failed to bind builtin component projection {class_name}"
            )

    for module_name, class_name in get_default_builtin_frame_pass_specs():
        module = importlib.import_module(module_name)
        cls = module.__dict__.get(class_name)
        if not isinstance(cls, type):
            raise RuntimeError(
                f"builtin frame-pass provider {module_name} does not expose class {class_name}"
            )
        if not tc_pass_registry_has(class_name):
            raise RuntimeError(
                f"builtin frame-pass descriptor {class_name} is not registered"
            )
        if not tc_pass_registry_bind_class_projection(class_name, cls):
            raise RuntimeError(
                f"failed to bind builtin frame-pass projection {class_name}"
            )


def bootstrap_player() -> None:
    """Bootstrap native roots, then publish builtin Python type projections."""
    _bootstrap_player_native()
    _publish_builtin_type_projections()


def bootstrap_editor() -> None:
    """Bootstrap editor registries and builtin Python type projections."""
    _bootstrap_editor_native()
    _publish_builtin_type_projections()


def configure_resource_manager_factory(factory: Callable[[], object] | None) -> None:
    """Set the process resource-manager factory during explicit bootstrap."""
    from termin_assets import set_resource_manager_factory

    set_resource_manager_factory(factory)


def _log_shutdown_error(scope: str, exc: Exception) -> None:
    try:
        from termin.base import log

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


def shutdown_runtime() -> None:
    """Release native process-global runtime registries."""
    _shutdown_runtime_native()


def shutdown_player() -> None:
    """Release player/runtime process-global registries and Python callbacks."""
    _run_shutdown_step("render pipelines", _shutdown_render_pipelines)
    _run_shutdown_step("Python render passes", _shutdown_python_passes)
    _run_shutdown_step("Python components", _shutdown_python_components)
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
