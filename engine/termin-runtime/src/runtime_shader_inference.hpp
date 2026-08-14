#pragma once

#include <string>
#include <utility>
#include <vector>

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

namespace termin::runtime::detail {
    void set_shader_material_ubo_layout_from_glsl(tc_shader* shader, const std::string& fragment_source);

    // Apply package-declared property kinds to the matching reflected fields.
    // The match is by the declared uniform name; kinds are never inferred from
    // naming conventions.  SrgbColor and LinearColor retain the vec4 payload.
    bool set_shader_material_ubo_property_types(
        tc_shader* shader,
        const std::vector<std::pair<std::string, std::string>>& properties,
        std::string& error);

    void set_shader_features_from_glsl(tc_shader* shader, const std::string& fragment_source);
} // namespace termin::runtime::detail
