#pragma once

#include <string>

extern "C"
{
#include <tgfx/resources/tc_shader.h>
}

namespace termin::runtime::detail
{
    void set_shader_material_ubo_layout_from_glsl(
        tc_shader* shader,
        const std::string& fragment_source);

    void set_shader_features_from_glsl(
        tc_shader* shader,
        const std::string& fragment_source);
}
