// material_pass.cpp - Post-processing pass using a Material.
//
// Fully migrated to tgfx2: wraps the output FBO as a tgfx2 texture,
// opens a ctx2 render pass, binds the material's own VS/FS through
// tc_shader_ensure_tgfx2, applies @property UBO via
// apply_material_phase_ubo_runtime (backend-neutral tgfx2 path), and draws the
// built-in fullscreen quad. No legacy GraphicsBackend draw calls.

#include <tcbase/tc_log.hpp>

#include <termin/render/frame_uniforms.hpp>
#include <termin/render/material_pass.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>
#include <termin/render/material_ubo_runtime.hpp>

#include <optional>

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
    tc_shader* shader = tc_shader_get(phase->shader);
    if (!shader) {
        tc::Log::warn("[MaterialPass] '%s': material has no valid shader",
                      get_pass_name().c_str());
        return;
    }

    tgfx::ShaderHandle vs2, fs2;
    if (!tc_shader_ensure_tgfx2(shader, &device, &vs2, &fs2)) {
        tc::Log::error("[MaterialPass] '%s': tc_shader_ensure_tgfx2 failed for shader '%s'",
                       get_pass_name().c_str(),
                       shader->name ? shader->name : shader->uuid);
        return;
    }

    ctx2->begin_pass(color_tex2, /*depth=*/{},
                     /*clear_color=*/nullptr,
                     /*clear_depth=*/1.0f,
                     /*clear_depth_enabled=*/false);
    ctx2->set_viewport(0, 0, w, h);
    ctx2->set_depth_test(false);
    ctx2->set_depth_write(false);
    ctx2->set_blend(false);
    ctx2->set_cull(tgfx::CullMode::None);

    ctx2->bind_shader(vs2, fs2);
    bind_engine_per_frame_uniforms(*ctx2, ctx);

    constexpr uint32_t MATERIAL_TEX_SLOT_BASE = 4;
    constexpr uint32_t EXTRA_TEX_SLOT_BASE = 9;
    uint32_t graph_tex_slot = EXTRA_TEX_SLOT_BASE;

    auto material_texture_slot = [&](const std::string& uniform_name) -> std::optional<uint32_t> {
        for (size_t i = 0; i < phase->texture_count; ++i) {
            if (uniform_name == phase->textures[i].name) {
                return MATERIAL_TEX_SLOT_BASE + static_cast<uint32_t>(i);
            }
        }
        return std::nullopt;
    };

    auto bind_graph_texture = [&](const std::string& res_name, const std::string& uniform_name) {
        if (res_name.empty() || uniform_name.empty()) return;
        auto res_it = ctx.tex2_reads.find(res_name);
        if (res_it != ctx.tex2_reads.end() && res_it->second) {
            uint32_t slot = graph_tex_slot;
            std::optional<uint32_t> material_slot = material_texture_slot(uniform_name);
            if (material_slot.has_value()) {
                slot = *material_slot;
            } else {
                if (graph_tex_slot > 15) {
                    tc::Log::error("[MaterialPass] '%s': no Vulkan descriptor slot left for '%s'",
                        get_pass_name().c_str(), uniform_name.c_str());
                    return;
                }
                graph_tex_slot++;
            }
            ctx2->bind_sampled_texture(slot, res_it->second);
            if (!material_slot.has_value()) {
                ctx2->set_uniform_int(uniform_name.c_str(), static_cast<int>(slot));
            }
        } else {
            tc::Log::warn("[MaterialPass] '%s': tgfx2 input texture for '%s' not available",
                get_pass_name().c_str(), res_name.c_str());
        }
    };

    if (shader->material_ubo_block_size > 0) {
        apply_material_phase_ubo_runtime(
            phase,
            shader,
            TC_MATERIAL_UBO_BINDING_SLOT,
            MATERIAL_TEX_SLOT_BASE,
            device,
            *ctx2);
    }

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
