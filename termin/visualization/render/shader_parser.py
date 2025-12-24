"""Shader parser - re-exported from C++ native module."""

from termin._native.render import (
    MaterialProperty,
    ShaderStage,
    ShaderPhase,
    ShaderMultyPhaseProgramm,
    parse_shader_text,
    parse_property_directive,
)

# Backward compatibility aliases
UniformProperty = MaterialProperty
ShasderStage = ShaderStage  # Legacy typo alias

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
