// shader_skinning.cpp - Slang shader skinning variants

#include "termin/render/shader_skinning.hpp"
#include <tcbase/tc_log.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unordered_set>

namespace termin {
namespace {

constexpr const char* SKINNED_MATERIAL_VARIANT_SHADER_UUID = "termin-engine-skinned-material";
constexpr const char* SKINNED_SHADOW_VARIANT_SHADER_UUID = "termin-engine-skinned-shadow";
constexpr const char* SKINNED_DEPTH_VARIANT_SHADER_UUID = "termin-engine-skinned-depth";
constexpr const char* SKINNED_ID_VARIANT_SHADER_UUID = "termin-engine-skinned-id";
constexpr const char* SKINNED_NORMAL_VARIANT_SHADER_UUID = "termin-engine-skinned-normal";

char* duplicate_c_string(const char* value) {
    if (!value) return nullptr;
    const size_t size = std::strlen(value) + 1;
    char* copy = static_cast<char*>(std::malloc(size));
    if (!copy) return nullptr;
    std::memcpy(copy, value, size);
    return copy;
}

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

TcShader create_slang_skinned_shader(
    const std::string& phase_mark,
    TcShader original_shader
) {
    const char* vertex_template_uuid = skinned_vertex_template_for_phase(phase_mark);
    const std::string vertex_source =
        tgfx::load_builtin_shader_stage_source_from_catalog(vertex_template_uuid, "vertex");
    if (vertex_source.empty()) {
        tc::Log::error(
            "[get_skinned_shader] failed to load Slang skinning vertex template '%s' for phase '%s'",
            vertex_template_uuid,
            phase_mark.c_str());
        return TcShader();
    }

    const char* fragment_source = original_shader.fragment_source();
    if (!fragment_source || fragment_source[0] == '\0') {
        tc::Log::error(
            "[get_skinned_shader] cannot create Slang skinning variant for '%s': fragment source is empty",
            original_shader.name());
        return TcShader();
    }

    const char* geometry_source = original_shader.geometry_source();
    if (geometry_source && geometry_source[0] != '\0') {
        tc::Log::error(
            "[get_skinned_shader] cannot create Slang skinning variant for '%s': geometry shaders are not supported",
            original_shader.name());
        return TcShader();
    }

    std::string orig_name = original_shader.name();
    std::string skinned_name = orig_name.empty()
        ? std::string("Skinned_") + original_shader.uuid()
        : orig_name + "_Skinned";
    if (!phase_mark.empty()) {
        skinned_name += "_" + phase_mark;
    }

    char variant_uuid[40];
    tc_shader_make_variant_uuid(
        variant_uuid,
        sizeof(variant_uuid),
        original_shader.uuid(),
        TC_SHADER_VARIANT_SKINNING);

    tc_shader_handle h = tc_shader_from_sources_ex(
        vertex_source.c_str(),
        fragment_source,
        nullptr,
        skinned_name.c_str(),
        original_shader.source_path(),
        variant_uuid,
        TC_SHADER_LANGUAGE_SLANG,
        TC_SHADER_ARTIFACT_REQUIRED);
    if (tc_shader_handle_is_invalid(h)) {
        tc::Log::error(
            "[get_skinned_shader] failed to create Slang skinned shader variant for '%s'",
            orig_name.c_str());
        return TcShader();
    }

    TcShader skinned(h);
    skinned.set_features(original_shader.features());
    skinned.set_language(TC_SHADER_LANGUAGE_SLANG);
    skinned.set_artifact_policy(TC_SHADER_ARTIFACT_REQUIRED);

    tc_shader* orig_raw = original_shader.get();
    tc_shader* skinned_raw = skinned.get();
    if (orig_raw && skinned_raw) {
        free(skinned_raw->vertex_entry);
        skinned_raw->vertex_entry = duplicate_c_string("vs_main");
        if (!skinned_raw->vertex_entry) {
            tc::Log::error(
                "[get_skinned_shader] failed to assign vertex entry for '%s'",
                skinned_name.c_str());
            tc_shader_destroy(h);
            return TcShader();
        }

        const char* fragment_entry = orig_raw->fragment_entry;
        if (!fragment_entry || fragment_entry[0] == '\0') {
            fragment_entry = "main";
        }
        free(skinned_raw->fragment_entry);
        skinned_raw->fragment_entry = duplicate_c_string(fragment_entry);
        if (!skinned_raw->fragment_entry) {
            tc::Log::error(
                "[get_skinned_shader] failed to assign fragment entry for '%s'",
                skinned_name.c_str());
            tc_shader_destroy(h);
            return TcShader();
        }

        // Slang skinned variants get material field layout from shaderc
        // sidecar reflection.
        tc_shader_set_material_ubo_layout(skinned_raw, nullptr, 0, 0);
    }

    skinned.set_variant_info(original_shader, TC_SHADER_VARIANT_SKINNING);
    return skinned;
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
        return create_slang_skinned_shader(phase_mark, original_shader);
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
