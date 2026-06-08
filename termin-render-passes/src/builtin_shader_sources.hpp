#pragma once

#include <string>

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin {

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

} // namespace termin
