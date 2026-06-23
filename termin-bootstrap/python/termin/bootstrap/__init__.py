"""Explicit startup bootstrap helpers for Termin programs."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_bootstrap")

from termin.bootstrap._bootstrap_native import (
    bootstrap_editor,
    bootstrap_player,
    bootstrap_runtime,
    init_inspect_adapters,
    init_pointer_extractors,
    init_python_component_callbacks,
    init_python_kind_handlers,
    register_runtime_kinds,
    register_scene_extensions,
)

__all__ = [
    "bootstrap_editor",
    "bootstrap_player",
    "bootstrap_runtime",
    "init_inspect_adapters",
    "init_pointer_extractors",
    "init_python_component_callbacks",
    "init_python_kind_handlers",
    "register_runtime_kinds",
    "register_scene_extensions",
]
