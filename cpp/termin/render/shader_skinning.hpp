#pragma once

// Shader skinning injection - automatically adds skeletal animation support to any shader.
// C++ implementation of termin/visualization/render/shader_skinning.py

#include <string>
#include "termin/render/tc_shader_handle.hpp"

namespace termin {

// Inject skinning code into a vertex shader source.
// Returns modified source with skinning support, or original if already has skinning.
std::string inject_skinning_into_vertex_shader(const std::string& vertex_source);

// Get or create a skinned variant of a shader.
// Returns skinned shader, or invalid shader if injection fails.
TcShader get_skinned_shader(TcShader original_shader);

} // namespace termin
