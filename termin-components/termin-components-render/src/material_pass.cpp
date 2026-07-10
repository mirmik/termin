// material_pass.cpp - Post-processing pass using a Material.
//
// Fully migrated to tgfx2: wraps the output FBO as a tgfx2 texture,
// opens a ctx2 render pass, prepares the material pipeline through the shared
// helpers, applies @property UBO via shader-reflected resources, and draws the
// built-in fullscreen quad with an explicit FSQ VS. No legacy GraphicsBackend
// draw calls.

#include <tcbase/tc_log.hpp>

#include <termin/render/material_pipeline.hpp>
#include <termin/render/material_pass.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/i_render_device.hpp>

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin {

uint32_t MaterialPass::s_quad_vao = 0;
uint32_t MaterialPass::s_quad_vbo = 0;

static tc_value string_map_to_tc_value(const std::unordered_map<std::string, std::string>& map) {
    tc_value result = tc_value_dict_new();
    for (const auto& [key, value] : map) {
        tc_value_dict_set(&result, key.c_str(), tc_value_string(value.c_str()));
    }
    return result;
}

static void tc_value_to_string_map(
    const tc_value* value,
    std::unordered_map<std::string, std::string>& out
) {
    out.clear();
    if (!value || value->type != TC_VALUE_DICT) {
        return;
    }

    for (size_t i = 0; i < tc_value_dict_size(value); ++i) {
        const char* key = nullptr;
        tc_value* item = tc_value_dict_get_at(const_cast<tc_value*>(value), i, &key);
        if (!key || !item || item->type != TC_VALUE_STRING || !item->data.s) {
            continue;
        }
        out[key] = item->data.s;
    }
}

static bool shader_has_material_field(const tc_shader* shader, const std::string& field_name) {
    if (!shader || field_name.empty()) {
        return false;
    }

    for (uint32_t i = 0; i < shader->material_ubo_entry_count; ++i) {
        if (field_name == shader->material_ubo_entries[i].name) {
            return true;
        }
    }

    const tc_shader_resource_binding* material_rb =
        tc_shader_find_resource_binding(shader, TC_SHADER_RESOURCE_MATERIAL);
    if (!material_rb ||
        material_rb->kind != TC_SHADER_RESOURCE_CONSTANT_BUFFER ||
        !material_rb->fields) {
        return false;
    }

    for (uint32_t i = 0; i < material_rb->field_count; ++i) {
        if (field_name == material_rb->fields[i].name) {
            return true;
        }
    }
    return false;
}

MaterialPass::MaterialPass() {
    pass_name_set("MaterialPass");
    link_to_type_registry("MaterialPass");
}

MaterialPass::~MaterialPass() {
    destroy();
}

tc_value MaterialPass::serialize_texture_resources() const {
    return string_map_to_tc_value(texture_resources);
}

void MaterialPass::deserialize_texture_resources(const tc_value* value) {
    tc_value_to_string_map(value, texture_resources);
}

tc_value MaterialPass::serialize_extra_resources() const {
    return string_map_to_tc_value(extra_resources);
}

void MaterialPass::deserialize_extra_resources(const tc_value* value) {
    tc_value_to_string_map(value, extra_resources);
}

void MaterialPass::set_texture_resource(const std::string& uniform_name, const std::string& resource_name) {
    texture_resources[uniform_name] = resource_name;
}

void MaterialPass::add_resource(const std::string& resource_name, const std::string& uniform_name) {
    std::string uname;
    if (uniform_name.empty()) {
        uname = "u_" + resource_name;
    } else if (uniform_name.rfind("u_", 0) != 0) {
        uname = "u_" + uniform_name;
    } else {
        uname = uniform_name;
    }
    extra_resources[resource_name] = uname;
}

void MaterialPass::remove_resource(const std::string& resource_name) {
    extra_resources.erase(resource_name);
}

std::set<const char*> MaterialPass::compute_reads() const {
    std::set<const char*> reads;

    if (!output_res_target.empty()) {
        reads.insert(output_res_target.c_str());
    }

    for (const auto& [res_name, uniform_name] : extra_resources) {
        (void)uniform_name;
        reads.insert(res_name.c_str());
    }

    for (const auto& [uniform_name, res_name] : texture_resources) {
        (void)uniform_name;
        if (!res_name.empty()) {
            reads.insert(res_name.c_str());
        }
    }

    return reads;
}

std::set<const char*> MaterialPass::compute_writes() const {
    return {output_res.c_str()};
}

bool MaterialPass::set_graph_resource_input(
    const std::string& socket_name,
    const std::string& resource_name
) {
    if (socket_name.empty() || resource_name.empty()) {
        return false;
    }
    if (socket_name == "output_res" || socket_name == "output_res_target") {
        return false;
    }

    std::string uniform_name = socket_name;
    if (uniform_name.rfind("u_", 0) != 0) {
        uniform_name = "u_" + uniform_name;
    }
    texture_resources[uniform_name] = resource_name;
    return true;
}

std::vector<std::pair<std::string, std::string>> MaterialPass::get_inplace_aliases() const {
    if (output_res_target.empty()) {
        return {};
    }
    return {{output_res_target, output_res}};
}

void MaterialPass::execute(ExecuteContext& ctx) {
    if (!enabled_get()) {
        return;
    }

    if (!ctx.ctx2) {
        tc::Log::error("[MaterialPass] '%s': ctx.ctx2 is null — MaterialPass is tgfx2-only",
                       get_pass_name().c_str());
        return;
    }
    auto* ctx2 = ctx.ctx2;
    auto& device = ctx2->device();

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        tc::Log::error("[MaterialPass] '%s': tgfx2 color texture for '%s' not available",
                       get_pass_name().c_str(), output_res.c_str());
        return;
    }
    tgfx::TextureHandle color_tex2 = color_it->second;

    auto out_desc = device.texture_desc(color_tex2);
    int w = static_cast<int>(out_desc.width);
    int h = static_cast<int>(out_desc.height);
    if (w <= 0 || h <= 0) return;

    tc_material* mat = material.get();
    if (!mat || mat->phase_count == 0) {
        tc::Log::error("[MaterialPass] '%s': material not set or has no phases",
            get_pass_name().c_str());
        return;
    }

    tc_material_phase* phase = &mat->phases[0];

    ctx2->begin_pass(color_tex2, /*depth=*/{},
                     /*clear_color=*/nullptr,
                     /*clear_depth=*/1.0f,
                     /*clear_depth_enabled=*/false);
    ctx2->set_viewport(0, 0, w, h);
    ctx2->set_depth_test(false);
    ctx2->set_depth_write(false);
    ctx2->set_blend(false);
    ctx2->set_cull(tgfx::CullMode::None);

    MaterialPipelineShaderBinding shader_binding{};
    if (!ensure_material_pipeline_shader(
            *ctx2,
            device,
            phase->shader,
            "MaterialPass",
            shader_binding)) {
        ctx2->end_pass();
        return;
    }
    // MaterialPass is a fullscreen post-process pass. Bind the canonical FSQ
    // vertex shader before resource preparation so D3D11 creates the pipeline
    // against the exact VS/FS pair that will draw. Relying on
    // draw_fullscreen_quad() to substitute the VS late can leave D3D11 with a
    // stale input/signature combination and collapses UVs to the top-left texel.
    ctx2->bind_shader(ctx2->fsq_vertex_shader(), shader_binding.fragment);
    ctx2->use_shader_resource_layout(shader_binding.shader);

    EnginePerFrameStd140 per_frame = make_engine_per_frame_uniforms(ctx);
    MaterialPipelineResourceView material_resources{};
    material_resources.per_frame = &per_frame;
    prepare_material_pipeline_resources(
        *ctx2,
        device,
        shader_binding.shader,
        phase,
        material_resources);

    auto bind_graph_texture = [&](
        const std::string& res_name,
        const std::string& uniform_name) {
        if (res_name.empty() || uniform_name.empty()) {
            return;
        }

        const tc_shader_resource_binding* rb =
            tc_shader_find_resource_binding(shader_binding.shader, uniform_name.c_str());
        if (!rb || rb->kind != TC_SHADER_RESOURCE_TEXTURE) {
            tc::Log::error(
                "[MaterialPass] '%s': texture uniform '%s' is not declared as a shader "
                "Texture2D resource; graph textures are bind-by-name only",
                get_pass_name().c_str(),
                uniform_name.c_str());
            return;
        }

        auto res_it = ctx.tex2_reads.find(res_name);
        if (res_it == ctx.tex2_reads.end() || !res_it->second) {
            tc::Log::warn("[MaterialPass] '%s': tgfx2 input texture for '%s' not available",
                get_pass_name().c_str(), res_name.c_str());
            return;
        }

        const std::string texel_size_uniform = uniform_name + "_texel_size";
        if (shader_has_material_field(shader_binding.shader, texel_size_uniform)) {
            tgfx::TextureDesc desc = device.texture_desc(res_it->second);
            if (desc.width > 0 && desc.height > 0) {
                const float texel_size[2] = {
                    1.0f / static_cast<float>(desc.width),
                    1.0f / static_cast<float>(desc.height),
                };
                if (!tc_material_phase_set_uniform(
                        phase,
                        texel_size_uniform.c_str(),
                        TC_UNIFORM_VEC2,
                        texel_size)) {
                    tc::Log::error(
                        "[MaterialPass] '%s': failed to update texture texel-size "
                        "material property '%s'",
                        get_pass_name().c_str(),
                        texel_size_uniform.c_str());
                }
            }
        }

        ctx2->bind_texture(uniform_name, res_it->second);
    };

    // extra_resources: pull tgfx2 color textures directly from ctx.tex2_reads.
    for (const auto& [res_name, uniform_name] : extra_resources) {
        bind_graph_texture(res_name, uniform_name);
    }

    // texture_resources: same tgfx2 texture lookup, keyed by uniform name.
    for (const auto& [uniform_name, res_name] : texture_resources) {
        bind_graph_texture(res_name, uniform_name);
    }

    // Built-in fullscreen quad VBO with layout (vec2 pos, vec2 uv) at
    // locations 0 and 1; shader stages must agree with the canonical
    // fullscreen varying contract.
    ctx2->draw_fullscreen_quad_with_bound_shader();

    ctx2->end_pass();
}

void MaterialPass::destroy() {
    material = TcMaterial();
    texture_resources.clear();
    extra_resources.clear();
}

TC_DEFINE_FRAME_PASS_FACTORY(MaterialPass);

void MaterialPass::register_type() {
    register_frame_pass_MaterialPass();
    _register_inspect_material();
    _register_inspect_output_res();
    _register_inspect_output_res_target();
    _register_inspect_metadata_graph();
    register_serialize_MaterialPass_texture_resources();
    register_serialize_MaterialPass_extra_resources();
}

} // namespace termin
