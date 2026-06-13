#pragma once

// Slang shader skinning variants.

#include <tgfx/tgfx_shader_handle.hpp>

namespace termin {

// Get or create a skinned variant of a shader.
// Returns an invalid shader if the source language or phase cannot be skinned.
TcShader get_skinned_shader(const std::string& phase_mark, TcShader original_shader);
TcShader get_skinned_shader(TcShader original_shader);

} // namespace termin
