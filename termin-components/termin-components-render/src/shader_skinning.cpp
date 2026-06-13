// shader_skinning.cpp - Slang shader skinning variants

#include "termin/render/shader_skinning.hpp"
#include "termin/render/material_pipeline.hpp"
#include <tcbase/tc_log.hpp>
#include <string>
#include <unordered_set>

namespace termin {
namespace {

constexpr const char* SKINNED_MATERIAL_VARIANT_SHADER_UUID = "termin-engine-skinned-material";
constexpr const char* SKINNED_SHADOW_VARIANT_SHADER_UUID = "termin-engine-skinned-shadow";
constexpr const char* SKINNED_DEPTH_VARIANT_SHADER_UUID = "termin-engine-skinned-depth";
constexpr const char* SKINNED_ID_VARIANT_SHADER_UUID = "termin-engine-skinned-id";
constexpr const char* SKINNED_NORMAL_VARIANT_SHADER_UUID = "termin-engine-skinned-normal";

const char* skinned_vertex_template_for_phase(const std::string& phase_mark) {
    if (phase_mark == "shadow") {
        return SKINNED_SHADOW_VARIANT_SHADER_UUID;
    }
    if (phase_mark == "depth") {
        return SKINNED_DEPTH_VARIANT_SHADER_UUID;
    }
    if (phase_mark == "pick") {
        return SKINNED_ID_VARIANT_SHADER_UUID;
    }
    if (phase_mark == "normal") {
        return SKINNED_NORMAL_VARIANT_SHADER_UUID;
    }
    return SKINNED_MATERIAL_VARIANT_SHADER_UUID;
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
        std::string suffix = "_Skinned";
        if (!phase_mark.empty()) {
            suffix += "_" + phase_mark;
        }

        MaterialVertexVariantRequest request{};
        request.original_shader = original_shader;
        request.variant_op = TC_SHADER_VARIANT_SKINNING;
        request.vertex_template_uuid = skinned_vertex_template_for_phase(phase_mark);
        request.variant_name_suffix = suffix.c_str();
        request.debug_context = "SkinnedMeshRenderer";
        request.vertex_entry = "vs_main";
        request.require_slang_original = true;
        return get_material_vertex_variant(request);
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
