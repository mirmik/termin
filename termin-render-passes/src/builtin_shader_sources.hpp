#pragma once

#include <string>

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin {

struct BuiltinShaderProgramSource {
    std::string name;
    std::string source;
};

std::string load_builtin_shader_source(const char* filename, const char* debug_name);
tc_shader_handle register_builtin_fragment_shader(
    const char* filename,
    const char* name,
    const char* uuid);
tc_shader_handle register_builtin_vertex_fragment_shader(
    const char* vertex_filename,
    const char* fragment_filename,
    const char* name,
    const char* uuid);
tc_shader_handle register_builtin_shader_from_catalog(const char* uuid);
BuiltinShaderProgramSource load_builtin_shader_program_from_catalog(const char* uuid);

} // namespace termin
