"""Compatibility import for canonical editor shader runtime configuration."""

from termin.editor_core.shader_runtime import (
    configure_sdk_shader_runtime,
    configure_shader_runtime,
    resolve_slangc,
    resolve_termin_shaderc,
)

__all__ = [
    "configure_sdk_shader_runtime",
    "configure_shader_runtime",
    "resolve_slangc",
    "resolve_termin_shaderc",
]
