"""Shader parser - canonical re-export from termin.materials."""

from termin.materials import (
    MaterialProperty,
    MaterialUboEntry,
    MaterialUboLayout,
    PhaseRenderSettings,
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
    "MaterialUboEntry",
    "MaterialUboLayout",
    "PhaseRenderSettings",
    "UniformProperty",
    "ShaderStage",
    "ShasderStage",
    "ShaderPhase",
    "ShaderMultyPhaseProgramm",
    "parse_shader_text",
    "parse_property_directive",
]
