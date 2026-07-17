#pragma once

// Slang shader skinning variants.

#include <string>

#include <termin/export.hpp>
#include <termin/render/material_pipeline_shader_assembler.hpp>

#include <tgfx/tgfx_shader_handle.hpp>

namespace termin {

// Conservative convenience contract for callers outside RenderTask planning.
ENTITY_API MaterialPipelinePassContract legacy_full_material_pass_contract();

ENTITY_API TcShader get_skinned_shader_for_pass(
    const MaterialPipelinePassContract& pass_contract,
    TcShader original_shader);

// Get or create a skinned variant of a shader.
// Returns an invalid shader if the source language cannot be skinned.
// Convenience overloads use a conservative full-material contract. Render
// passes select variants through the mesh RenderItem task planner instead.
ENTITY_API TcShader get_skinned_shader(const std::string& phase_mark, TcShader original_shader);
ENTITY_API TcShader get_skinned_shader(TcShader original_shader);

} // namespace termin
