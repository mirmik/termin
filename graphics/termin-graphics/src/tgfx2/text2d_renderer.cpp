// text2d_renderer.cpp - Pixel-space text rendering on tgfx2.
//
// Port of termin-graphics/python/tgfx/text2d.py.
//
// Vertex layout matches RenderContext2::draw_immediate_triangles
// (7 floats per vertex: vec3 pos + vec4 misc). The fragment shader
// re-interprets the misc block as (u, v, _, _).

#include "tgfx2/text2d_renderer.hpp"

#include "tgfx2/builtin_shader_sources.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <vector>

#include "tgfx2/font_atlas.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader.h>
#include <tgfx/resources/tc_shader_registry.h>
}

#include <tcbase/tc_log.hpp>
#include <tcbase/profiler_scope.hpp>

#include "internal/utf8_decode.hpp"
#include "internal/screen_text_geometry.hpp"

extern "C" {
#include "tgfx/tgfx2_interop.h"
}

namespace tgfx {

    namespace {

        constexpr const char* TEXT2D_SHADER_UUID = "termin-engine-text2d";
        constexpr const char* TEXT2D_SDF_SHADER_UUID = "termin-engine-text2d-sdf";
        constexpr float kFullBitmapCoverageCorrectionPx = 14.0f;
        constexpr float kNeutralBitmapCoverageCorrectionPx = 24.0f;

        float bitmap_coverage_gamma_for_size(float configured_gamma, float display_px, termin::LinearColor color) {
            if (configured_gamma == 0.0f) {
                // Calibrated against grayscale UI text on contrasting backgrounds.
                // Dark ink needs stronger partial coverage. Bright white on black
                // is already well represented by linear-light blending.
                const float luminance = std::clamp(0.2126f * color.r + 0.7152f * color.g + 0.0722f * color.b,
                                                   0.0f, 1.0f);
                constexpr float light = Text2DRenderer::kDefaultBitmapCoverageGamma;
                configured_gamma = luminance < 0.5f
                    ? std::lerp(1.0f / light, light, luminance * 2.0f)
                    : std::lerp(light, 1.0f, (luminance - 0.5f) * 2.0f);
            }
            const float correction =
                std::clamp((kNeutralBitmapCoverageCorrectionPx - display_px) /
                               (kNeutralBitmapCoverageCorrectionPx - kFullBitmapCoverageCorrectionPx),
                           0.0f,
                           1.0f);
            return 1.0f + (configured_gamma - 1.0f) * correction;
        }

        // mat4 + vec4 + scalar, padded to std140 vec4 alignment.
        struct Text2DPushData {
            float projection[16];
            float color[4];
            float coverage_gamma;
            float _pad[3];
        };
        static_assert(sizeof(Text2DPushData) == 96, "Text2DPushData layout drift — shader and C++ disagree");

        // SDF push constants: mat4 + vec4 + float, padded to std140 vec4 alignment.
        struct Text2DSdfPushData {
            float projection[16];
            float color[4];
            float smoothing;
            float _pad[3];
        };
        static_assert(sizeof(Text2DSdfPushData) == 96, "Text2DSdfPushData layout drift — shader and C++ disagree");

        // Build an ortho matrix (column-major) that maps pixel coords y+down
        // → clip-space y+down (Vulkan-native; OpenGL reaches this via
        // glClipControl(GL_UPPER_LEFT), which tgfx2 re-applies at the start
        // of every render pass in OpenGLCommandList::begin_render_pass).
        // Pixel (0,0) maps to clip (-1,-1), i.e. the top-left corner.
        //
        // The matrix is written in math (row-major) notation but stored in the
        // push-constant layout expected by the shader.
        void build_ortho_pixel_to_ndc(float w, float h, float out[16]) {
            if (w <= 0.0f || h <= 0.0f) {
                std::memset(out, 0, 16 * sizeof(float));
                out[0] = out[5] = out[10] = out[15] = 1.0f;
                return;
            }
            float m[16]{};
            m[0] = 2.0f / w;
            m[3] = -1.0f;
            m[5] = 2.0f / h;
            m[7] = -1.0f;
            m[10] = 1.0f;
            m[15] = 1.0f;
            std::memcpy(out, m, sizeof(m));
        }

    } // namespace

    // ---------------------------------------------------------------------------

    Text2DRenderer::Text2DRenderer(FontAtlas* font)
        : font_(font) {}

    Text2DRenderer::~Text2DRenderer() {
        // Best-effort release. If the device is already gone we can't
        // destroy shaders — just drop the handles and leak; the process
        // is going down anyway.
        release_gpu();
    }

    void Text2DRenderer::ensure_shader_(IRenderDevice& device) {
        vs_ = ShaderHandle{};
        fs_ = ShaderHandle{};
        termin::Tgfx2ShaderView bitmap_view;
        if (termin::builtin_shader_resolve_tgfx2(TEXT2D_SHADER_UUID, &shader_handle_, &device, &bitmap_view)) {
            vs_ = bitmap_view.vertex_shader;
            fs_ = bitmap_view.fragment_shader;
        } else {
            tc::Log::error("[Text2DRenderer] failed to resolve bitmap shader");
        }

        if (vs_.id == 0 || fs_.id == 0) {
            tc::Log::error("[Text2DRenderer] bitmap shader is unavailable");
        }

        vs_sdf_ = ShaderHandle{};
        fs_sdf_ = ShaderHandle{};
        termin::Tgfx2ShaderView sdf_view;
        if (termin::builtin_shader_resolve_tgfx2(TEXT2D_SDF_SHADER_UUID, &sdf_shader_handle_, &device, &sdf_view)) {
            vs_sdf_ = sdf_view.vertex_shader;
            fs_sdf_ = sdf_view.fragment_shader;
        } else {
            tc::Log::error("[Text2DRenderer] failed to resolve SDF shader");
        }

        if (vs_sdf_.id == 0 || fs_sdf_.id == 0) {
            tc::Log::error("[Text2DRenderer] SDF shader is unavailable");
        }
    }

    void Text2DRenderer::release_gpu() {
        // Shaders live on the tc_shader registry (`shader_handle_`) and are
        // shared across Text2DRenderer instances — nothing to destroy here.
        // Cached handles (vs_/fs_) are just local views into the slot's
        // current tgfx2 ids, stale after the device goes away.
        vs_ = ShaderHandle{};
        fs_ = ShaderHandle{};
        vs_sdf_ = ShaderHandle{};
        fs_sdf_ = ShaderHandle{};
        ctx_ = nullptr;
    }

    void Text2DRenderer::begin(RenderContext2* ctx, int viewport_w, int viewport_h, FontAtlas* font) {
        if (font != nullptr)
            font_ = font;
        ctx_ = ctx;

        if (ctx_ != nullptr) {
            ensure_shader_(ctx_->device());
        }

        // Cache the projection matrix so draw() can rebind every call
        // without re-computing. draw() must rebind shader + atlas +
        // projection on every call because callers may interleave Text2D
        // draws with other draws that change the bound shader.
        build_ortho_pixel_to_ndc(static_cast<float>(viewport_w), static_cast<float>(viewport_h), proj_);
    }

    namespace {

        void append_glyph_quad(std::vector<Text2DVertex>& vertices,
                               const termin::Affine2f& basis,
                               termin::Vec2f top_left,
                               float width, float height, float u0, float v0, float u1, float v1) {
            const auto right = basis.transform_vector({width, 0});
            const auto down = basis.transform_vector({0, height});
            const Text2DVertex a{top_left, {u0, v0}};
            const Text2DVertex b{top_left + down, {u0, v1}};
            const Text2DVertex c{top_left + down + right, {u1, v1}};
            const Text2DVertex d{top_left + right, {u1, v0}};
            vertices.insert(vertices.end(), {a, b, c, a, c, d});
        }

        termin::Vec2f anchor_offset(float width, float height, float line_px,
                                    TextAnchor2D anchor, TextVerticalAnchor2D vertical_anchor) {
            float x = 0.0f;
            if (anchor == TextAnchor2D::Center)
                x = -0.5f * width;
            else if (anchor == TextAnchor2D::Right)
                x = -width;

            float y = 0.0f;
            if (vertical_anchor == TextVerticalAnchor2D::Center)
                y = -0.5f * height;
            else if (vertical_anchor == TextVerticalAnchor2D::Default && anchor == TextAnchor2D::Center)
                y = -0.5f * line_px;
            return {x, y};
        }

    } // namespace

    std::vector<Text2DVertex> internal::screen_text_vertices(FontAtlas& font,
                                                             std::string_view text,
                                                             ScreenFontSize size,
                                                             const termin::Affine2f& raster_to_screen,
                                                             TextAnchor2D anchor,
                                                             TextVerticalAnchor2D vertical_anchor,
                                                             bool snap_sdf_origin) {
        tc::ProfilerScope profile("text.build_quads");
        std::vector<Text2DVertex> vertices;
        if (font.is_sdf_size(size.line_px)) {
            font.ensure_glyphs(text, size.line_px);
            const float width = font.measure_text(text, size.line_px).width;
            const float ref = static_cast<float>(font.sdf_reference_px());
            const float scale = size.line_px / ref;
            const float height = font.line_height_px(ref) * scale;
            const auto offset = anchor_offset(width, height, size.line_px, anchor, vertical_anchor);
            auto origin = raster_to_screen.transform_point(offset);
            if (snap_sdf_origin) {
                origin.x = std::floor(origin.x + 0.5f);
                origin.y = std::floor(origin.y + 0.5f);
            }

            const float spread = font.sdf_spread() * scale;
            float pen = 0.0f;
            std::size_t i = 0;
            while (i < text.size()) {
                const auto glyph = font.get_glyph(utf8_decode(text, i), size.line_px);
                if (!glyph)
                    continue;
                const auto top_left = origin + raster_to_screen.transform_vector({pen + glyph->offset_x_px, -spread});
                append_glyph_quad(vertices, raster_to_screen, top_left, glyph->width_px, glyph->height_px,
                                  glyph->u0, glyph->v0, glyph->u1, glyph->v1);
                pen += glyph->advance_px;
            }
            return vertices;
        }

        const auto run = font.layout_bitmap_text(text, size.em_px);
        vertices.reserve(run.glyphs.size() * 6);
        auto offset = anchor_offset(run.width_px, run.height_px, size.line_px, anchor, vertical_anchor);
        offset.y += run.ascent_px;
        const auto baseline = raster_to_screen.transform_point(offset);
        // Rotation, reflection, shear and anisotropic scaling need the original
        // affine geometry. Grid fitting is valid only for a one-to-one mask.
        const bool screen_grid = raster_to_screen.m00 == 1.0f && raster_to_screen.m11 == 1.0f &&
                                 raster_to_screen.m01 == 0.0f && raster_to_screen.m10 == 0.0f;
        for (const auto& placed : run.glyphs) {
            auto pen = baseline + raster_to_screen.transform_vector({placed.x_px, placed.y_px});
            unsigned phase = 0;
            if (screen_grid) {
                const float floor_x = std::floor(pen.x);
                constexpr auto phases = FontAtlas::kBitmapPhaseCount;
                const auto nearest = static_cast<unsigned>((pen.x - floor_x) * phases + 0.5f);
                pen.x = floor_x + static_cast<float>(nearest / phases);
                pen.y = std::floor(pen.y + 0.5f);
                phase = nearest % phases;
            }
            const auto glyph = font.bitmap_glyph(placed.glyph_id, size.em_px, phase);
            if (!glyph || glyph->width_px == 0 || glyph->height_px == 0)
                continue;
            const auto top_left = pen + raster_to_screen.transform_vector({glyph->offset_x_px, glyph->offset_y_px});
            append_glyph_quad(vertices, raster_to_screen, top_left, glyph->width_px, glyph->height_px,
                              glyph->u0, glyph->v0, glyph->u1, glyph->v1);
        }
        return vertices;
    }

    void Text2DRenderer::draw(std::string_view text_utf8, const DrawOptions& options, FontAtlas* font) {
        draw(text_utf8, options, FontSizeUnit::LineHeight, font);
    }

    void Text2DRenderer::draw(std::string_view text_utf8, const DrawOptions& options, FontSizeUnit size_unit,
                              FontAtlas* font) {
        FontAtlas* active_font = font ? font : font_;
        if (text_utf8.empty() || active_font == nullptr || ctx_ == nullptr)
            return;
        if (!std::isfinite(options.size) || options.size <= 0.0f ||
            !std::isfinite(options.x) || !std::isfinite(options.y)) {
            tc::Log::error("[Text2DRenderer] text requires finite coordinates and a positive finite size");
            return;
        }
        const internal::ScreenFontSize size{*active_font, options.size, size_unit};
        const auto vertices = internal::screen_text_vertices(*active_font, text_utf8, size,
                                                             termin::Affine2f::translation(options.x, options.y),
                                                             static_cast<TextAnchor2D>(options.anchor),
                                                             TextVerticalAnchor2D::Default, true);
        draw_mesh(vertices, options.color, size.line_px, active_font, options.coverage_gamma);
    }

    void Text2DRenderer::draw_mesh(std::span<const Text2DVertex> vertices,
                                   termin::SrgbColor color,
                                   float display_px,
                                   FontAtlas* font,
                                   std::optional<float> coverage_gamma) {
        draw_mesh_linear(vertices, termin::srgb_to_linear(color), display_px, font, coverage_gamma);
    }

    void Text2DRenderer::draw_mesh_linear(std::span<const Text2DVertex> vertices,
                                          termin::LinearColor color,
                                          float display_px,
                                          FontAtlas* font,
                                          std::optional<float> coverage_gamma) {
        if (vertices.empty() || vertices.size() % 3 != 0 || font == nullptr || ctx_ == nullptr) {
            return;
        }
        if (coverage_gamma.has_value() && (!std::isfinite(*coverage_gamma) || *coverage_gamma <= 0.0f)) {
            tc::Log::error("[Text2DRenderer] per-mesh coverage gamma must be finite and positive");
            return;
        }
        ensure_shader_(ctx_->device());

        RenderContext2& ctx = *ctx_;
        const bool use_sdf = font->is_sdf_size(display_px);
        const ShaderHandle selected_vs = use_sdf ? vs_sdf_ : vs_;
        const ShaderHandle selected_fs = use_sdf ? fs_sdf_ : fs_;
        if (selected_vs.id == 0 || selected_fs.id == 0) {
            tc::Log::error("[Text2DRenderer] %s shader is unavailable; skipping text mesh", use_sdf ? "SDF" : "bitmap");
            return;
        }

        tc_shader* raw = nullptr;
        if (use_sdf) {
            ctx.bind_shader(selected_vs, selected_fs);
            raw = tc_shader_get(sdf_shader_handle_);
            Text2DSdfPushData push{};
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    push.projection[col * 4 + row] = proj_[row * 4 + col];
                }
            }
            push.color[0] = color.r;
            push.color[1] = color.g;
            push.color[2] = color.b;
            push.color[3] = color.a;
            push.smoothing = 1.0f / (2.0f * static_cast<float>(font->sdf_spread()));
            ctx.use_shader_resource_layout(raw);
            ctx.bind_uniform_data("text2d_sdf_draw", &push, static_cast<uint32_t>(sizeof(push)));
        } else {
            ctx.bind_shader(selected_vs, selected_fs);
            raw = tc_shader_get(shader_handle_);
            Text2DPushData push{};
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    push.projection[col * 4 + row] = proj_[row * 4 + col];
                }
            }
            push.color[0] = color.r;
            push.color[1] = color.g;
            push.color[2] = color.b;
            push.color[3] = color.a;
            push.coverage_gamma =
                coverage_gamma.value_or(bitmap_coverage_gamma_for_size(bitmap_coverage_gamma_, display_px, color));
            ctx.use_shader_resource_layout(raw);
            ctx.bind_uniform_data("text2d_draw", &push, static_cast<uint32_t>(sizeof(push)));
        }

        {
            tc::ProfilerScope profile("text.ensure_texture");
            const TextureHandle atlas = use_sdf ? font->sdf_atlas_texture(&ctx) : font->ensure_texture(&ctx);
            ctx.bind_texture("u_font_atlas", atlas);
        }

        std::vector<float> packed;
        packed.reserve(vertices.size() * 7);
        for (const auto& vertex : vertices) {
            packed.insert(packed.end(),
                          {vertex.position.x, vertex.position.y, 0.0f, vertex.uv.x, vertex.uv.y, 0.0f, 0.0f});
        }
        ctx.draw_immediate_triangles(packed.data(), static_cast<uint32_t>(vertices.size()));
    }

    void Text2DRenderer::end() {
        ctx_ = nullptr;
    }

    void Text2DRenderer::set_bitmap_coverage_gamma(float gamma) {
        if (!std::isfinite(gamma) || gamma <= 0.0f) {
            tc::Log::error("[Text2DRenderer] bitmap coverage gamma must be finite and positive");
            throw std::invalid_argument("Text2DRenderer bitmap coverage gamma must be finite and positive");
        }
        bitmap_coverage_gamma_ = gamma;
    }

} // namespace tgfx
