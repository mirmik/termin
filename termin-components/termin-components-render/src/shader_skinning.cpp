// shader_skinning.cpp - Slang shader skinning variants

#include "termin/render/shader_skinning.hpp"
#include "termin/render/material_pipeline.hpp"
#include <tcbase/tc_log.hpp>
#include <string>
#include <unordered_set>

namespace termin {
namespace {

MaterialPipelinePassContract legacy_material_pass_contract()
{
    MaterialPipelinePassContract contract;
    contract.debug_name = "legacy_material";
    contract.required_material_fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.uses_material_fragment = true;

    MaterialFragmentInterface fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.static_vertex_transform =
        material_pipeline_make_static_vertex_transform_contract(
            "static",
            material_pipeline_full_material_mesh_input(),
            fragment_input,
            material_pipeline_common_vertex_resources("draw_data"));
    contract.skinned_vertex_transform =
        material_pipeline_make_skinned_vertex_transform_contract(
            *contract.static_vertex_transform,
            "skinned",
            "termin-engine-skinned-material",
            material_pipeline_skinned_material_mesh_input());
    return contract;
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

TcShader get_skinned_shader_for_pass(
    const MaterialPipelinePassContract& pass_contract,
    TcShader original_shader)
{
    if (!original_shader.is_valid()) {
        return TcShader();
    }
    if (original_shader.language() == TC_SHADER_LANGUAGE_SLANG) {
        if (!pass_contract.skinned_vertex_transform.has_value()) {
            if (should_log_unsupported_skinning_shader(pass_contract.debug_name, original_shader)) {
                tc::Log::error(
                    "[get_skinned_shader] pass '%s' has no skinned vertex transform contract",
                    pass_contract.debug_name.c_str());
            }
            return TcShader();
        }

        MaterialShaderOverrideRequest request{};
        request.original_shader = original_shader;
        request.vertex_transform_kind = VertexTransformKind::SkinnedMesh;
        request.pass_contract = pass_contract;
        request.vertex_transform_contract = pass_contract.skinned_vertex_transform;
        request.shader_variant_op = TC_SHADER_VARIANT_SKINNING;
        request.debug_context = "SkinnedMeshRenderer";
        return assemble_material_shader_override(request);
    }
    if (should_log_unsupported_skinning_shader(pass_contract.debug_name, original_shader)) {
        tc::Log::error(
            "[get_skinned_shader] Shader '%s' uses unsupported source language %u; "
            "skinning variants require Slang material shaders",
            original_shader.name(),
            static_cast<unsigned>(original_shader.language()));
    }
    return TcShader();
}

TcShader get_skinned_shader(const std::string& phase_mark, TcShader original_shader) {
    (void)phase_mark;
    return get_skinned_shader_for_pass(
        legacy_material_pass_contract(),
        original_shader);
}

TcShader get_skinned_shader(TcShader original_shader) {
    return get_skinned_shader_for_pass(
        legacy_material_pass_contract(),
        original_shader);
}

} // namespace termin
