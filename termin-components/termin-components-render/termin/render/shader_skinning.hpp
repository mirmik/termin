#pragma once

// Slang shader skinning variants.

#include <string>

#include <termin/export.hpp>
#include <termin/render/material_pipeline_shader_assembler.hpp>

#include <tgfx/tgfx_shader_handle.hpp>

namespace termin {

// Compatibility contract for legacy Drawable::override_shader callers that do
// not receive a pass-owned MaterialPipelinePassContract. New pass-owned code
// should pass an explicit contract through ShaderOverrideContext instead.
ENTITY_API MaterialPipelinePassContract legacy_full_material_pass_contract();

ENTITY_API TcShader get_skinned_shader_for_pass(
    const MaterialPipelinePassContract& pass_contract,
    TcShader original_shader);

// Get or create a skinned variant of a shader.
// Returns an invalid shader if the source language cannot be skinned.
// Compatibility overloads use a conservative full-material contract because
// the legacy Drawable override ABI does not carry pass-owned shader intent.
// Pass-owned code should call get_skinned_shader_for_pass instead.
ENTITY_API TcShader get_skinned_shader(const std::string& phase_mark, TcShader original_shader);
ENTITY_API TcShader get_skinned_shader(TcShader original_shader);

} // namespace termin
