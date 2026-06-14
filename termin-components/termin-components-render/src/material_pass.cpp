// material_pass.cpp - Post-processing pass using a Material.
//
// Fully migrated to tgfx2: wraps the output FBO as a tgfx2 texture,
// opens a ctx2 render pass, binds the material's own VS/FS through the shared
// material pipeline helpers, applies @property UBO via shader-reflected
// resources, and draws the built-in fullscreen quad. No legacy GraphicsBackend
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

    EnginePerFrameStd140 per_frame = make_engine_per_frame_uniforms(ctx);
    MaterialPipelineResourceContext material_resources{};
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
    ctx2->draw_fullscreen_quad();

    ctx2->end_pass();
}

void MaterialPass::destroy() {
    material = TcMaterial();
    texture_resources.clear();
    extra_resources.clear();
}

TC_REGISTER_FRAME_PASS(MaterialPass);

} // namespace termin
