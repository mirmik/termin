// shader_skinning.cpp - Slang shader skinning variants

#include "termin/render/shader_skinning.hpp"
#include "termin/render/material_pipeline.hpp"
#include <tcbase/tc_log.hpp>
#include <string>
#include <unordered_set>

namespace termin {
namespace {

MaterialPipelinePassKind pass_kind_for_phase(const std::string& phase_mark)
{
    if (phase_mark == "shadow") {
        return MaterialPipelinePassKind::Shadow;
    }
    if (phase_mark == "depth") {
        return MaterialPipelinePassKind::Depth;
    }
    if (phase_mark == "pick") {
        return MaterialPipelinePassKind::Id;
    }
    if (phase_mark == "normal") {
        return MaterialPipelinePassKind::Normal;
    }
    return MaterialPipelinePassKind::Color;
}

bool should_log_unsupported_skinning_shader(
    const std::string& phase_mark,
    TcShader original_shader
) {
    static std::unordered_set<std::string> logged_keys;
    std::string key = phase_mark;
    key += '|';
    key += original_shader.uuid();
    key += '|';
    key += std::to_string(static_cast<unsigned>(original_shader.language()));
    return logged_keys.insert(key).second;
}

} // namespace

TcShader get_skinned_shader(const std::string& phase_mark, TcShader original_shader) {
    if (!original_shader.is_valid()) {
        return TcShader();
    }
    if (original_shader.language() == TC_SHADER_LANGUAGE_SLANG) {
        MaterialShaderOverrideRequest request{};
        request.original_shader = original_shader;
        request.vertex_transform_kind = VertexTransformKind::SkinnedMesh;
        request.pass_kind = pass_kind_for_phase(phase_mark);
        request.shader_variant_op = TC_SHADER_VARIANT_SKINNING;
        request.debug_context = "SkinnedMeshRenderer";
        return assemble_material_shader_override(request);
    }
    if (should_log_unsupported_skinning_shader(phase_mark, original_shader)) {
        tc::Log::error(
            "[get_skinned_shader] Shader '%s' uses unsupported source language %u; "
            "skinning variants require Slang material shaders",
            original_shader.name(),
            static_cast<unsigned>(original_shader.language()));
    }
    return TcShader();
}

TcShader get_skinned_shader(TcShader original_shader) {
    return get_skinned_shader("", original_shader);
}

} // namespace termin
