// bloom_pass.cpp - HDR bloom post-processing pass implementation.
//
// Draws through tgfx::RenderContext2: bright prefilter, separable Gaussian
// downsample chain, normalized reconstruction and composite, with HDR
// (RGBA16F) intermediate textures, std140 UBOs for parameters and reflected
// texture bindings for all sampler slots. Legacy tgfx1 dual-path removed in
// Stage 8.1.
#include "termin/render/execute_context.hpp"
#include <termin/render/bloom_pass.hpp>

#include "tgfx2/builtin_shader_sources.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

#include <algorithm>
#include <span>
#include <tcbase/tc_log.hpp>

namespace termin {

    constexpr const char* BLOOM_BRIGHT_SHADER_UUID = "termin-engine-bloom-bright";
    constexpr const char* BLOOM_DOWNSAMPLE_SHADER_UUID = "termin-engine-bloom-downsample";
    constexpr const char* BLOOM_BLUR_VERTICAL_SHADER_UUID = "termin-engine-bloom-blur-vertical";
    constexpr const char* BLOOM_UPSAMPLE_SHADER_UUID = "termin-engine-bloom-upsample";
    constexpr const char* BLOOM_COMPOSITE_SHADER_UUID = "termin-engine-bloom-composite";

    // Shader source lives in termin-graphics/resources/builtin_shaders and is
    // registered here by UUID so editor/runtime draws consume the same source that
    // package export uses for artifact generation.

    // ================================================================
    // std140-packed UBO structs
    // ================================================================

    struct BloomBrightParamsStd140 {
        float texel_x;
        float texel_y;
        float threshold;
        float soft_threshold;
    };
    static_assert(sizeof(BloomBrightParamsStd140) == 16, "std140 alignment");

    struct BloomDownsampleParamsStd140 {
        float texel_x;
        float texel_y;
        float _pad[2];
    };
    static_assert(sizeof(BloomDownsampleParamsStd140) == 16, "std140 alignment");

    struct BloomUpsampleParamsStd140 {
        float texel_x;
        float texel_y;
        float scatter;
        float _pad;
    };
    static_assert(sizeof(BloomUpsampleParamsStd140) == 16, "std140 alignment");

    struct BloomCompositeParamsStd140 {
        float intensity;
        float _pad[3];
    };
    static_assert(sizeof(BloomCompositeParamsStd140) == 16, "std140 alignment");

    // ================================================================
    // BloomPass implementation
    // ================================================================

    BloomPass::BloomPass(const std::string& input,
                         const std::string& output,
                         float threshold_val,
                         float soft_threshold_val,
                         float intensity_val,
                         int mip_levels_val,
                         float scatter_val)
        : input_res(input),
          output_res(output),
          threshold(threshold_val),
          soft_threshold(soft_threshold_val),
          intensity(intensity_val),
          mip_levels(mip_levels_val),
          scatter(scatter_val) {
        pass_name_set("Bloom");
        link_to_type_registry("BloomPass");
    }

    std::set<const char*> BloomPass::compute_reads() const {
        std::set<const char*> reads;
        if (!input_res.empty()) {
            reads.insert(input_res.c_str());
        }
        if (!output_res_target.empty()) {
            reads.insert(output_res_target.c_str());
        }
        return reads;
    }

    std::set<const char*> BloomPass::compute_writes() const {
        return {output_res.c_str()};
    }

    std::vector<std::pair<std::string, std::string>> BloomPass::get_inplace_aliases() const {
        if (output_res_target.empty()) {
            return {};
        }
        return {{output_res_target, output_res}};
    }

    // ----------------------------------------------------------------------------
    // tgfx2 path
    // ----------------------------------------------------------------------------

    void BloomPass::ensure_tgfx2_shaders() {
        // FS-only TcShaders (vertex_source is NULL; VS comes from ctx2's
        // built-in FSQ). Hash-based dedup keeps compiled VkShaderModules
        // across pass re-creations — see ShadowPass for the matching
        // pattern on VS+FS passes, and GrayscalePass for the FS-only variant.
        if (tc_shader_handle_is_invalid(bright_shader_handle_)) {
            bright_shader_handle_ = tgfx::register_builtin_shader_from_catalog(BLOOM_BRIGHT_SHADER_UUID);
        }
        if (tc_shader_handle_is_invalid(downsample_shader_handle_)) {
            downsample_shader_handle_ = tgfx::register_builtin_shader_from_catalog(BLOOM_DOWNSAMPLE_SHADER_UUID);
        }
        if (tc_shader_handle_is_invalid(blur_vertical_shader_handle_)) {
            blur_vertical_shader_handle_ = tgfx::register_builtin_shader_from_catalog(BLOOM_BLUR_VERTICAL_SHADER_UUID);
        }
        if (tc_shader_handle_is_invalid(upsample_shader_handle_)) {
            upsample_shader_handle_ = tgfx::register_builtin_shader_from_catalog(BLOOM_UPSAMPLE_SHADER_UUID);
        }
        if (tc_shader_handle_is_invalid(composite_shader_handle_)) {
            composite_shader_handle_ = tgfx::register_builtin_shader_from_catalog(BLOOM_COMPOSITE_SHADER_UUID);
        }

        auto make_ubo = [&](uint64_t size) -> tgfx::BufferHandle {
            tgfx::BufferDesc desc;
            desc.size = size;
            desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
            return device2_->create_buffer(desc);
        };

        if (!bright_ubo_)
            bright_ubo_ = make_ubo(sizeof(BloomBrightParamsStd140));
        if (!downsample_ubo_)
            downsample_ubo_ = make_ubo(sizeof(BloomDownsampleParamsStd140));
        if (!upsample_ubo_)
            upsample_ubo_ = make_ubo(sizeof(BloomUpsampleParamsStd140));
        if (!composite_ubo_)
            composite_ubo_ = make_ubo(sizeof(BloomCompositeParamsStd140));
    }

    static tgfx::ShaderHandle bloom_resolve_fs(tc_shader_handle h,
                                               tgfx::IRenderDevice* device,
                                               const char* name,
                                               ::tc_shader** out_raw = nullptr) {
        tc_shader* raw = tc_shader_get(h);
        if (out_raw)
            *out_raw = raw;
        tgfx::ShaderHandle fs;
        if (!raw || !tc_shader_ensure_tgfx2(raw, device, nullptr, &fs)) {
            tc::Log::error("BloomPass: tc_shader_ensure_tgfx2 failed for %s", name);
            return {};
        }
        return fs;
    }

    void BloomPass::destroy_tgfx2_mip_textures() {
        if (!device2_) {
            mip_textures_.clear();
            reconstruction_textures_.clear();
            resolve_texture_ = {};
            return;
        }
        for (auto& t : mip_textures_) {
            if (t)
                device2_->destroy(t);
        }
        for (auto& t : reconstruction_textures_) {
            if (t)
                device2_->destroy(t);
        }
        if (resolve_texture_) {
            device2_->destroy(resolve_texture_);
            resolve_texture_ = {};
        }
        mip_textures_.clear();
        reconstruction_textures_.clear();
    }

    void BloomPass::ensure_tgfx2_mip_textures(int width, int height) {
        int count = std::max(1, std::min(mip_levels, 8));
        bool need_recreate =
            (width != last_tgfx2_width_) || (height != last_tgfx2_height_) || (count != last_tgfx2_mip_levels_);
        if (!need_recreate && !mip_textures_.empty())
            return;

        destroy_tgfx2_mip_textures();

        last_tgfx2_width_ = width;
        last_tgfx2_height_ = height;
        last_tgfx2_mip_levels_ = count;

        for (int i = 0; i < count; i++) {
            // Bloom starts at half resolution. Besides reducing bandwidth, the
            // filtered prepass prevents a one-pixel HDR source from entering the
            // reconstruction pyramid as a hard grid-aligned impulse.
            int mip_w = std::max(1, width >> (i + 1));
            int mip_h = std::max(1, height >> (i + 1));

            tgfx::TextureDesc desc;
            desc.width = mip_w;
            desc.height = mip_h;
            desc.mip_levels = 1;
            desc.sample_count = 1;
            desc.format = tgfx::PixelFormat::RGBA16F;
            desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::Sampled;
            mip_textures_.push_back(device2_->create_texture(desc));
            // Unity's Gaussian path uses its "up" chain as the horizontal
            // temporary, then reuses it as the reconstruction destination.
            reconstruction_textures_.push_back(device2_->create_texture(desc));
        }

        tgfx::TextureDesc resolve_desc;
        resolve_desc.width = std::max(1, width >> 1);
        resolve_desc.height = std::max(1, height >> 1);
        resolve_desc.mip_levels = 1;
        resolve_desc.sample_count = 1;
        resolve_desc.format = tgfx::PixelFormat::RGBA16F;
        resolve_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::Sampled;
        resolve_texture_ = device2_->create_texture(resolve_desc);
    }

    // Helper — common FSQ draw setup for tgfx2 sub-passes. Sets render state,
    // binds the built-in FSQ VS + the provided FS, sets vertex layout. Caller
    // is responsible for begin_pass / set_viewport / bind_uniform_buffer /
    // reflected texture binding / draw_fullscreen_quad / end_pass around this.
    static void setup_fsq_state(tgfx::RenderContext2& ctx, tgfx::ShaderHandle fs) {
        ctx.set_depth_test(false);
        ctx.set_depth_write(false);
        ctx.set_blend(false);
        ctx.set_cull(tgfx::CullMode::None);

        ctx.bind_shader(ctx.fsq_vertex_shader(), fs);

        tgfx::VertexLayoutDesc fsq_layout;
        fsq_layout.stride = 4 * sizeof(float);
        fsq_layout.attribute_count = 2;
        fsq_layout.attributes[0] = {0, tgfx::VertexFormat::Float2, 0, tgfx::intern_vertex_semantic("position")};
        fsq_layout.attributes[1] = {
            1, tgfx::VertexFormat::Float2, 2 * sizeof(float), tgfx::intern_vertex_semantic("uv")};
        ctx.set_vertex_layout(fsq_layout);
    }

    void BloomPass::execute(ExecuteContext& ctx) {
        if (!ctx.ctx2) {
            tc::Log::error("[BloomPass] ctx.ctx2 is null — BloomPass is tgfx2-only");
            return;
        }
        auto in_it = ctx.tex2_reads.find(input_res);
        if (in_it == ctx.tex2_reads.end() || !in_it->second) {
            tc::Log::error("[BloomPass/tgfx2] Missing tgfx2 input texture handle '%s'", input_res.c_str());
            return;
        }
        tgfx::TextureHandle input_tex2 = in_it->second;

        auto out_it = ctx.tex2_writes.find(output_res);
        if (out_it == ctx.tex2_writes.end() || !out_it->second) {
            tc::Log::error("[BloomPass/tgfx2] Missing tgfx2 output texture handle '%s'", output_res.c_str());
            return;
        }
        tgfx::TextureHandle output_tex2 = out_it->second;

        auto out_desc = ctx.ctx2->device().texture_desc(output_tex2);
        const int w = static_cast<int>(out_desc.width);
        const int h = static_cast<int>(out_desc.height);
        if (w <= 0 || h <= 0)
            return;

        const int count = std::max(1, std::min(mip_levels, 8));

        if (!device2_) {
            device2_ = &ctx.ctx2->device();
        }
        ensure_tgfx2_shaders();
        ensure_tgfx2_mip_textures(w, h);
        if (mip_textures_.empty()) {
            tc::Log::error("[BloomPass/tgfx2] Failed to create mip textures");
            return;
        }

        auto& c2 = *ctx.ctx2;

        tc_shader* bright_raw = nullptr;
        tc_shader* downsample_raw = nullptr;
        tc_shader* blur_vertical_raw = nullptr;
        tc_shader* upsample_raw = nullptr;
        tc_shader* composite_raw = nullptr;
        tgfx::ShaderHandle bright_fs = bloom_resolve_fs(bright_shader_handle_, device2_, "bright", &bright_raw);
        tgfx::ShaderHandle downsample_fs =
            bloom_resolve_fs(downsample_shader_handle_, device2_, "downsample", &downsample_raw);
        tgfx::ShaderHandle blur_vertical_fs =
            bloom_resolve_fs(blur_vertical_shader_handle_, device2_, "blur_vertical", &blur_vertical_raw);
        tgfx::ShaderHandle upsample_fs = bloom_resolve_fs(upsample_shader_handle_, device2_, "upsample", &upsample_raw);
        tgfx::ShaderHandle composite_fs =
            bloom_resolve_fs(composite_shader_handle_, device2_, "composite", &composite_raw);
        if (!bright_fs || !downsample_fs || !blur_vertical_fs || !upsample_fs || !composite_fs) {
            return;
        }

        // === 1. Bright Pass -> mip[0] ===
        {
            BloomBrightParamsStd140 p{};
            p.texel_x = 1.0f / static_cast<float>(w);
            p.texel_y = 1.0f / static_cast<float>(h);
            p.threshold = threshold;
            p.soft_threshold = soft_threshold;
            device2_->upload_buffer(bright_ubo_,
                                    std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

            c2.begin_pass(mip_textures_[0]);
            c2.set_viewport(0, 0, std::max(1, w >> 1), std::max(1, h >> 1));
            setup_fsq_state(c2, bright_fs);
            c2.use_shader_resource_layout(bright_raw);
            c2.bind_uniform("u_params", bright_ubo_);
            c2.bind_texture("u_texture", input_tex2);
            c2.draw_fullscreen_quad();
            c2.end_pass();
        }

        // === 2. Progressive separable Gaussian downsample ===
        //
        // This follows Unity URP's Gaussian path: a nine-tap horizontal filter
        // downsamples into temporary mipUp[i], then an optimized five-sample
        // vertical filter writes the final mipDown[i].
        for (int i = 1; i < count && i < (int)mip_textures_.size(); i++) {
            int src_w = std::max(1, w >> i);
            int src_h = std::max(1, h >> i);
            int dst_w = std::max(1, w >> (i + 1));
            int dst_h = std::max(1, h >> (i + 1));

            BloomDownsampleParamsStd140 p{};
            p.texel_x = 2.0f / static_cast<float>(src_w);
            p.texel_y = 2.0f / static_cast<float>(src_h);
            device2_->upload_buffer(downsample_ubo_,
                                    std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

            c2.begin_pass(reconstruction_textures_[i]);
            c2.set_viewport(0, 0, dst_w, dst_h);
            setup_fsq_state(c2, downsample_fs);
            c2.use_shader_resource_layout(downsample_raw);
            c2.bind_uniform("u_params", downsample_ubo_);
            c2.bind_texture("u_texture", mip_textures_[i - 1]);
            c2.draw_fullscreen_quad();
            c2.end_pass();

            p.texel_x = 1.0f / static_cast<float>(dst_w);
            p.texel_y = 1.0f / static_cast<float>(dst_h);
            device2_->upload_buffer(downsample_ubo_,
                                    std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

            c2.begin_pass(mip_textures_[i]);
            c2.set_viewport(0, 0, dst_w, dst_h);
            setup_fsq_state(c2, blur_vertical_fs);
            c2.use_shader_resource_layout(blur_vertical_raw);
            c2.bind_uniform("u_params", downsample_ubo_);
            c2.bind_texture("u_texture", reconstruction_textures_[i]);
            c2.draw_fullscreen_quad();
            c2.end_pass();
        }

        // === 3. Progressive Upsample ===
        //
        // Reconstruct into separate targets instead of relying on framebuffer
        // load + additive blending. The normalized interpolation keeps bloom
        // energy stable when mip_levels changes: levels control radius, scatter
        // controls how much of the wider, lower-resolution bloom is retained.
        for (int i = count - 2; i >= 0; i--) {
            if (i + 1 >= (int)mip_textures_.size())
                continue;

            int src_w = std::max(1, w >> (i + 2));
            int src_h = std::max(1, h >> (i + 2));
            int dst_w = std::max(1, w >> (i + 1));
            int dst_h = std::max(1, h >> (i + 1));
            tgfx::TextureHandle low_res = (i + 1 == count - 1) ? mip_textures_[i + 1] : reconstruction_textures_[i + 1];

            BloomUpsampleParamsStd140 p{};
            p.texel_x = 1.0f / static_cast<float>(src_w);
            p.texel_y = 1.0f / static_cast<float>(src_h);
            // Match Unity's public Scatter control: keep a small contribution
            // from both sides even at the inspector endpoints.
            p.scatter = 0.05f + 0.90f * std::clamp(scatter, 0.0f, 1.0f);
            device2_->upload_buffer(upsample_ubo_,
                                    std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

            c2.begin_pass(reconstruction_textures_[i]);
            c2.set_viewport(0, 0, dst_w, dst_h);
            setup_fsq_state(c2, upsample_fs);
            c2.use_shader_resource_layout(upsample_raw);
            c2.bind_uniform("u_params", upsample_ubo_);
            c2.bind_texture("u_high", mip_textures_[i]);
            c2.bind_texture("u_low", low_res);
            c2.draw_fullscreen_quad();
            c2.end_pass();
        }

        tgfx::TextureHandle bloom_texture = count > 1 ? reconstruction_textures_[0] : mip_textures_[0];

        // Termin's fullscreen blit convention accumulates a subpixel phase shift
        // across the mip pyramid. Resolve once with a separable Gaussian at half
        // resolution so that the reconstructed point-spread function stays
        // continuous instead of exposing diagonal mip-grid lobes.
        {
            const int bloom_w = std::max(1, w >> 1);
            const int bloom_h = std::max(1, h >> 1);
            const tgfx::TextureHandle horizontal_target = count > 1 ? mip_textures_[0] : reconstruction_textures_[0];
            BloomDownsampleParamsStd140 p{};
            p.texel_x = 1.0f / static_cast<float>(bloom_w);
            p.texel_y = 1.0f / static_cast<float>(bloom_h);
            device2_->upload_buffer(downsample_ubo_,
                                    std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

            c2.begin_pass(horizontal_target);
            c2.set_viewport(0, 0, bloom_w, bloom_h);
            setup_fsq_state(c2, downsample_fs);
            c2.use_shader_resource_layout(downsample_raw);
            c2.bind_uniform("u_params", downsample_ubo_);
            c2.bind_texture("u_texture", bloom_texture);
            c2.draw_fullscreen_quad();
            c2.end_pass();

            c2.begin_pass(resolve_texture_);
            c2.set_viewport(0, 0, bloom_w, bloom_h);
            setup_fsq_state(c2, blur_vertical_fs);
            c2.use_shader_resource_layout(blur_vertical_raw);
            c2.bind_uniform("u_params", downsample_ubo_);
            c2.bind_texture("u_texture", horizontal_target);
            c2.draw_fullscreen_quad();
            c2.end_pass();
            bloom_texture = resolve_texture_;
        }

        // === 4. Composite Pass (input + resolved bloom -> output) ===
        {
            BloomCompositeParamsStd140 p{};
            p.intensity = intensity;
            device2_->upload_buffer(composite_ubo_,
                                    std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&p), sizeof(p)));

            c2.begin_pass(output_tex2);
            c2.set_viewport(0, 0, w, h);
            setup_fsq_state(c2, composite_fs);
            c2.use_shader_resource_layout(composite_raw);
            c2.bind_uniform("u_params", composite_ubo_);
            c2.bind_texture("u_original", input_tex2);
            c2.bind_texture("u_bloom", bloom_texture);
            c2.draw_fullscreen_quad();
            c2.end_pass();
        }
    }

    void BloomPass::destroy() {
        if (device2_) {
            destroy_tgfx2_mip_textures();
            // FS shaders live on the tc_shader registry (`*_shader_handle_`),
            // shared across pass re-creations — not owned here.
            if (bright_ubo_)
                device2_->destroy(bright_ubo_);
            if (downsample_ubo_)
                device2_->destroy(downsample_ubo_);
            if (upsample_ubo_)
                device2_->destroy(upsample_ubo_);
            if (composite_ubo_)
                device2_->destroy(composite_ubo_);
            bright_ubo_ = {};
            downsample_ubo_ = {};
            upsample_ubo_ = {};
            composite_ubo_ = {};
            device2_ = nullptr;
        }
        last_tgfx2_width_ = 0;
        last_tgfx2_height_ = 0;
        last_tgfx2_mip_levels_ = 0;
    }

    void BloomPass::register_type() {
        auto descriptor = FramePassTypeDescriptorBuilder::native<BloomPass>("BloomPass", "termin-render-passes");
        auto& inspect = descriptor.inspect();
        _register_inspect_input_res(inspect);
        _register_inspect_output_res(inspect);
        _register_inspect_output_res_target(inspect);
        _register_inspect_threshold(inspect);
        _register_inspect_soft_threshold(inspect);
        _register_inspect_intensity(inspect);
        _register_inspect_mip_levels(inspect);
        _register_inspect_scatter(inspect);
        _register_inspect_metadata_graph(inspect);
        (void)descriptor.commit();
    }

} // namespace termin
