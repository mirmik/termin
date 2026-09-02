// skybox_pass.cpp - Skybox rendered fully through RenderContext2 + material UBO.
#include "termin/render/skybox_pass.hpp"

#include "termin/materials/shader_parser.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/render_camera.hpp"
#include "termin/render/scene_render_services.hpp"

#include "tgfx2/builtin_shader_sources.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

#include <core/tc_scene_render_state.h>
#include <core/tc_scene_skybox.h>

#include <termin/geom/color.hpp>
#include <tcbase/tc_log.hpp>

#include <cstring>
#include <vector>

namespace termin {

    tc_scene_skybox resolve_skybox_for_render(tc_scene_skybox authored, tc_srgb_color background) {
        if (authored.type == TC_SKYBOX_NONE) {
            authored.type = TC_SKYBOX_SOLID;
            authored.color = background;
        }
        return authored;
    }

    constexpr const char* SKYBOX_ENGINE_SHADER_UUID = "termin-engine-skybox";

    // ============================================================================
    // Shader source
    // ============================================================================
    //
    // Full @program .shader text is loaded from the built-in shader resources.
    // The parser processes it at load time and
    // synthesizes a std140 MaterialParams block from the @property entries,
    // strips the corresponding `uniform` decls from the stage sources, and
    // injects the block declaration after #version. The layout, block size,
    // and rewritten stage sources all come out of parse_shader_text() below.
    //
    // A single fragment stage branches on u_skybox_type to cover both solid
    // and gradient variants, so the program compiles to one pipeline.

    // ============================================================================
    // Construction
    // ============================================================================

    SkyBoxPass::SkyBoxPass(const std::string& input, const std::string& output, const std::string& pass_name)
        : input_res(input),
          output_res(output) {
        pass_name_set(pass_name.c_str());
        link_to_type_registry("SkyBoxPass");
    }

    std::set<const char*> SkyBoxPass::compute_reads() const {
        return {input_res.c_str()};
    }

    std::set<const char*> SkyBoxPass::compute_writes() const {
        return {output_res.c_str()};
    }

    std::vector<ResourceSpec> SkyBoxPass::get_resource_specs() const {
        // The pass covers the complete target. Keep the allocator fallback
        // neutral in case drawing fails; authored scene background is resolved
        // and drawn explicitly in execute().
        ResourceSpec spec;
        spec.resource = input_res;
        spec.clear_color = termin::LinearColor{0.0f, 0.0f, 0.0f, 1.0f};
        spec.clear_depth = 1.0f;
        return {spec};
    }

    // ============================================================================
    // Lazy resource creation
    // ============================================================================

    void SkyBoxPass::ensure_resources(ExecuteContext& ctx) {
        if (!tc_shader_handle_is_invalid(skybox_shader_handle_))
            return;
        if (!ctx.ctx2)
            return;

        device2_ = &ctx.ctx2->device();

        // Parse the @program .shader text once. Parser auto-generates the
        // std140 MaterialParams block from the @property entries, rewrites
        // the stage sources to include the block declaration, and returns a
        // layout we can use directly for std140_pack / block_size sizing.
        const tgfx::BuiltinShaderProgramSource shader_program =
            tgfx::load_builtin_shader_program_from_catalog(SKYBOX_ENGINE_SHADER_UUID);
        if (shader_program.source.empty()) {
            return;
        }
        ShaderMultyPhaseProgramm parsed = parse_shader_text(shader_program.source);
        if (parsed.phases.empty()) {
            tc::Log::error("[SkyBoxPass] failed to parse shader text");
            return;
        }
        const ShaderPhase& phase = parsed.phases.front();
        skybox_layout_ = phase.material_ubo_layout;
        if (skybox_layout_.block_size == 0) {
            tc::Log::error("[SkyBoxPass] parser produced empty material UBO layout");
            return;
        }

        const auto vs_it = phase.stages.find("vertex");
        const auto fs_it = phase.stages.find("fragment");
        if (vs_it == phase.stages.end() || fs_it == phase.stages.end()) {
            tc::Log::error("[SkyBoxPass] parser produced phase without vertex/fragment stage");
            return;
        }

        // Process-lifetime engine shader — hash-dedup keeps one handle
        // across pass re-creations, compiled VkShaderModule stays cached.
        skybox_shader_handle_ = tc_shader_register_static_uuid_ex(vs_it->second.source.c_str(),
                                                                  fs_it->second.source.c_str(),
                                                                  nullptr,
                                                                  shader_program.name.c_str(),
                                                                  SKYBOX_ENGINE_SHADER_UUID,
                                                                  TC_SHADER_LANGUAGE_SLANG,
                                                                  TC_SHADER_ARTIFACT_REQUIRED);
        if (tc_shader* raw = tc_shader_get(skybox_shader_handle_)) {
            std::vector<tc_material_ubo_entry> entries;
            entries.reserve(skybox_layout_.entries.size());
            for (const auto& src : skybox_layout_.entries) {
                tc_material_ubo_entry entry{};
                std::strncpy(entry.name, src.name.c_str(), TC_MATERIAL_UBO_NAME_MAX - 1);
                entry.name[TC_MATERIAL_UBO_NAME_MAX - 1] = '\0';
                std::strncpy(entry.property_type, src.property_type.c_str(), TC_MATERIAL_UBO_TYPE_MAX - 1);
                entry.property_type[TC_MATERIAL_UBO_TYPE_MAX - 1] = '\0';
                entry.offset = src.offset;
                entry.size = src.size;
                entries.push_back(entry);
            }
            tc_shader_set_material_ubo_layout(
                raw, entries.data(), static_cast<uint32_t>(entries.size()), skybox_layout_.block_size);
        }
    }

    // ============================================================================
    // Execute
    // ============================================================================

    void SkyBoxPass::execute(ExecuteContext& ctx) {
        (void)execute_impl(ctx, false);
    }

    bool SkyBoxPass::get_raster_contract(ExecuteContext& ctx, tc_raster_pass_contract& out_contract) const {
        out_contract = {};
        out_contract.struct_size = sizeof(out_contract);
        out_contract.target_resource = output_res.c_str();
        out_contract.view_count = 1;
        out_contract.color_load = TC_RASTER_LOAD;
        out_contract.depth_load = TC_RASTER_CLEAR;
        const auto color = ctx.tex2_writes.find(output_res);
        const auto depth = ctx.tex2_depth_writes.find(output_res);
        out_contract.has_color = color != ctx.tex2_writes.end() && static_cast<bool>(color->second);
        // SkyBox itself does not test depth, but the fused ColorPass which
        // follows it does. The first contract owns the physical scope, so it
        // must attach and initialize depth for all later logical passes.
        out_contract.has_depth = depth != ctx.tex2_depth_writes.end() && static_cast<bool>(depth->second);
        out_contract.attachment_barrier_after = false;
        out_contract.fusion_eligible = true;
        return !output_res.empty() && out_contract.has_color;
    }

    bool SkyBoxPass::record_raster(ExecuteContext& ctx) {
        return execute_impl(ctx, true);
    }

    bool SkyBoxPass::execute_impl(ExecuteContext& ctx, bool raster_scope_already_open) {
        if (!ctx.ctx2) {
            tc::Log::error("[SkyBoxPass] ctx2 is null — tgfx2 path required");
            return false;
        }
        const SceneRenderServices* services = require_scene_render_services(ctx, "SkyBoxPass");
        if (!services)
            return false;
        tc_scene_handle scene = services->scene.handle();

        tc_scene_skybox authored_skybox{};
        if (const tc_scene_skybox* skybox = tc_scene_get_skybox(scene)) {
            authored_skybox = *skybox;
        }
        tc_srgb_color background{};
        tc_scene_get_background_srgb_color(scene, &background);
        const tc_scene_skybox skybox = resolve_skybox_for_render(authored_skybox, background);
        const int skybox_type = skybox.type;

        auto out_it = ctx.tex2_writes.find(output_res);
        if (out_it == ctx.tex2_writes.end() || !out_it->second) {
            tc::Log::error("[SkyBoxPass] no tgfx2 output texture for '%s'", output_res.c_str());
            return false;
        }
        tgfx::TextureHandle output_tex2 = out_it->second;

        auto out_desc = ctx.ctx2->device().texture_desc(output_tex2);
        const int w = static_cast<int>(out_desc.width);
        const int h = static_cast<int>(out_desc.height);
        if (w <= 0 || h <= 0)
            return false;

        const RenderCamera* primary_view = ctx.view.primary_view();
        if (!primary_view) {
            tc::Log::error("[SkyBoxPass] primary render view is missing");
            return false;
        }

        ensure_resources(ctx);
        if (skybox_layout_.block_size == 0)
            return false;

        // Collect material values: variant selector + camera matrices + colors.
        // u_skybox_type is a shader-local variant selector (0=gradient, 1=solid).
        // The fragment shader branches on it so we bind one pipeline regardless
        // of variant. u_skybox_type = Int here, not Bool, so the shader comparison
        // uses GLSL int semantics.
        int variant_int = (skybox_type == TC_SKYBOX_SOLID) ? 1 : 0;

        Vec3f solid_rgb{0, 0, 0};
        Vec3f top_rgb{0, 0, 0};
        Vec3f horizon_rgb{0, 0, 0};
        Vec3f bot_rgb{0, 0, 0};
        tc_srgb_color solid_color{};
        tc_srgb_color top_color{};
        tc_srgb_color horizon_color{};
        tc_srgb_color bottom_color{};
        solid_color = skybox.color;
        top_color = skybox.top_color;
        horizon_color = skybox.horizon_color;
        bottom_color = skybox.bottom_color;
        solid_rgb = {solid_color.r, solid_color.g, solid_color.b};
        top_rgb = {top_color.r, top_color.g, top_color.b};
        horizon_rgb = {horizon_color.r, horizon_color.g, horizon_color.b};
        bot_rgb = {bottom_color.r, bottom_color.g, bottom_color.b};
        const float top_exponent = skybox.top_exponent;
        const float bottom_exponent = skybox.bottom_exponent;

        Mat44 view64 = primary_view->get_view_matrix();
        Mat44 proj64 = primary_view->get_projection_matrix();
        Mat44 inv_view_projection64 = (proj64 * view64).inverse();

        std::vector<double> inv_view_projection_data(inv_view_projection64.data, inv_view_projection64.data + 16);

        std::vector<MaterialProperty> values;
        values.emplace_back("u_inv_view_projection", "Mat4", std::move(inv_view_projection_data));
        values.emplace_back("u_skybox_type", "Int", variant_int);
        values.emplace_back(
            "u_skybox_color", "SrgbColor", std::vector<double>{solid_rgb.x, solid_rgb.y, solid_rgb.z, 1.0});
        values.emplace_back(
            "u_skybox_top_color", "SrgbColor", std::vector<double>{top_rgb.x, top_rgb.y, top_rgb.z, 1.0});
        values.emplace_back("u_skybox_horizon_color",
                            "SrgbColor",
                            std::vector<double>{horizon_rgb.x, horizon_rgb.y, horizon_rgb.z, 1.0});
        values.emplace_back(
            "u_skybox_bottom_color", "SrgbColor", std::vector<double>{bot_rgb.x, bot_rgb.y, bot_rgb.z, 1.0});
        values.emplace_back("u_skybox_top_exponent", "Float", static_cast<double>(top_exponent));
        values.emplace_back("u_skybox_bottom_exponent", "Float", static_cast<double>(bottom_exponent));

        // Standalone execution owns its render pass. The normal framegraph path
        // fuses SkyBoxPass with the following scene-color pass, preserving the
        // authored background in one physical attachment scope on tile-based
        // and WebGL backends.
        if (!raster_scope_already_open) {
            tgfx::RenderPassDesc pass;
            tgfx::ColorAttachmentDesc color;
            color.texture = output_tex2;
            color.load = tgfx::LoadOp::Load;
            color.store = tgfx::StoreOp::Store;
            pass.colors.push_back(color);
            if (!ctx.ctx2->begin_pass(pass)) {
                tc::Log::error("[SkyBoxPass] failed to begin standalone raster pass");
                return false;
            }
        }
        ctx.ctx2->set_viewport(0, 0, w, h);

        // The skybox draw itself neither tests nor writes depth. A fused
        // physical raster pass may still own and clear the depth attachment for
        // the following scene-color draw.
        ctx.ctx2->set_depth_test(false);
        ctx.ctx2->set_depth_write(false);
        ctx.ctx2->set_depth_func(tgfx::CompareOp::LessEqual);
        ctx.ctx2->set_blend(false);
        ctx.ctx2->set_cull(tgfx::CullMode::None);

        tgfx::ShaderHandle sky_vs, sky_fs;
        tc_shader* raw = tc_shader_get(skybox_shader_handle_);
        if (!raw || !tc_shader_ensure_tgfx2(raw, device2_, &sky_vs, &sky_fs)) {
            tc::Log::error("SkyBoxPass: tc_shader_ensure_tgfx2 failed for engine skybox shader");
            if (!raster_scope_already_open)
                ctx.ctx2->end_pass();
            return false;
        }

        ctx.ctx2->clear_resource_bindings();
        ctx.ctx2->bind_shader(sky_vs, sky_fs);
        ctx.ctx2->use_shader_resource_layout(raw);

        std::vector<uint8_t> material_data(skybox_layout_.block_size, 0);
        std140_pack(skybox_layout_, values, material_data.data());
        if (!params_ubo_) {
            tgfx::BufferDesc desc;
            desc.size = material_data.size();
            desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
            params_ubo_ = device2_->create_buffer(desc);
            if (!params_ubo_) {
                tc::Log::error("[SkyBoxPass] failed to allocate material UBO");
                if (!raster_scope_already_open)
                    ctx.ctx2->end_pass();
                return false;
            }
        }
        device2_->upload_buffer(params_ubo_, material_data);
        ctx.ctx2->bind_uniform(TC_SHADER_RESOURCE_MATERIAL, params_ubo_);

        ctx.ctx2->draw_fullscreen_quad_with_bound_shader();
        if (!raster_scope_already_open)
            ctx.ctx2->end_pass();
        return true;
    }

    void SkyBoxPass::destroy() {
        if (device2_) {
            // skybox_shader_handle_ is static engine shader — not released.
            if (params_ubo_)
                device2_->destroy(params_ubo_);
            params_ubo_ = {};
            device2_ = nullptr;
        }
        skybox_layout_ = MaterialUboLayout{};
    }

    void SkyBoxPass::register_type() {
        auto descriptor = FramePassTypeDescriptorBuilder::native<SkyBoxPass>("SkyBoxPass", "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_input_res(inspect);
        _register_inspect_output_res(inspect);
        _register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

} // namespace termin
