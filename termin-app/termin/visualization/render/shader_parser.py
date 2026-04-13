"""Shader parser - re-exported from C++ native module."""

from termin._native.render import (
    MaterialProperty,
    UniformProperty,
    ShaderStage,
    ShasderStage,
    ShaderPhase,
    ShaderMultyPhaseProgramm,
    parse_shader_text,
    parse_property_directive,
)

__all__ = [
    "MaterialProperty",
    "UniformProperty",
    "ShaderStage",
    "ShasderStage",
    "ShaderPhase",
    "ShaderMultyPhaseProgramm",
    "parse_shader_text",
    "parse_property_directive",
]
