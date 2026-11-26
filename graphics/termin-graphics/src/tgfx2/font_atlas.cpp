#include "tgfx2/font_atlas.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <vector>

#include <ft2build.h>
#include FT_FREETYPE_H
#include <hb-ot.h>
#include <hb.h>

extern "C" {
#include <tc_profiler.h>
#include <tcbase/tc_log.h>
}

#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/render_context.hpp"

#include "internal/utf8_decode.hpp"

// stb_truetype - single-header; define the implementation in this TU
// only. The header itself lives at termin-thirdparty/stb/.
#define STB_TRUETYPE_IMPLEMENTATION
#define STBTT_STATIC
#include "stb_truetype.h"

namespace tgfx {

    namespace {

        // Same ~140 preload characters as tgfx/font.py. Keeping the set
        // identical means "first-frame glyph misses" of any Python code path
        // translate 1:1 to the C++ port — no surprise rasterisations on the
        // first real frame. Preload only runs at `default_preload_size_` —
        // other sizes populate lazily on first use.
        static const char* kPreloadUtf8 =
            // ASCII printable (U+0020..U+007E)
            " !\"#$%&'()*+,-./0123456789:;<=>?@"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`"
            "abcdefghijklmnopqrstuvwxyz{|}~"
            // Symbols from Python preload.
            "\xE2\x96\xB6\xE2\x96\xBC\xE2\x96\xB2\xE2\x97\x80" // ▶▼▲◀
            "\xE2\x96\xA0\xE2\x96\xA1\xE2\x96\xA3\xE2\x96\xAB" // ■□▣▫
            "\xE2\x97\x8B\xE2\x97\x8F\xE2\x97\x88\xE2\x97\x86" // ○●◈◆
            "\xE2\x80\xA2\xE2\x80\xA3\xE2\x97\xA6"             // •‣◦
            "\xE2\x9C\x93\xE2\x9C\x97\xE2\x9C\x95"             // ✓✗✕
            "\xE2\x96\xB7\xE2\x96\xBD\xE2\x97\x81\xE2\x96\xB3" // ▷▽◁△
            "\xE2\x86\x90\xE2\x86\x92\xE2\x86\x91\xE2\x86\x93" // ←→↑↓
            "\xE2\x8C\x82";                                    // ⌂

        std::vector<uint8_t> read_file_bytes(const std::string& path) {
            std::ifstream f(path, std::ios::binary | std::ios::ate);
            if (!f) {
                throw std::runtime_error("FontAtlas: cannot open " + path);
            }
            auto size = f.tellg();
            if (size <= 0 || size > std::numeric_limits<int>::max()) {
                throw std::runtime_error("FontAtlas: unsupported font file size for " + path);
            }
            f.seekg(0, std::ios::beg);
            std::vector<uint8_t> bytes(static_cast<size_t>(size));
            if (size > 0 && !f.read(reinterpret_cast<char*>(bytes.data()), size)) {
                throw std::runtime_error("FontAtlas: failed to read " + path);
            }
            return bytes;
        }

    } // namespace

    struct FontAtlas::Impl {
        std::vector<uint8_t> ttf_bytes;
        stbtt_fontinfo font{};
        FT_Library ft_library = nullptr;
        FT_Face ft_face = nullptr;
        FT_F26Dot6 current_em = 0;
        hb_font_t* shaping_font = nullptr;
        std::unordered_map<uint64_t, BitmapGlyph> screen_glyphs;
        // Font vmetrics in font-design units. We stash them here so each
        // per-size metrics resolution is a cheap multiply without touching
        // stb again.
        int ascent_u = 0;
        int descent_u = 0; // stb convention: negative

        ~Impl() {
            if (shaping_font)
                hb_font_destroy(shaping_font);
            if (ft_face)
                FT_Done_Face(ft_face);
            if (ft_library)
                FT_Done_FreeType(ft_library);
        }
    };

    // ---------------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------------

    int FontAtlas::quantise_size_(float display_px) {
        // Round to nearest integer px, clamp to the minimum. No bucketing
        // beyond that — start simple, tighten later if atlas pressure
        // forces it. See header kMinPxSize.
        int px = static_cast<int>(std::lround(display_px));
        if (px < kMinPxSize)
            px = kMinPxSize;
        return px;
    }

    const FontAtlas::SizeMetrics& FontAtlas::metrics_for_(int px_size) const {
        auto it = size_metrics_.find(px_size);
        if (it != size_metrics_.end())
            return it->second;

        // Glyph storage is already bounded by the bitmap/SDF atlas dimensions.
        // Keep the much smaller per-integer-size metrics cache bounded as well so
        // repeated presentation-scale changes cannot grow it for process life.
        if (size_metrics_.size() >= kMaxCachedMetricSizes) {
            size_metrics_.erase(size_metrics_.begin());
        }
        SizeMetrics sm{};
        sm.scale = stbtt_ScaleForPixelHeight(&impl_->font, static_cast<float>(px_size));
        // Match Python: line_height = ascent + descent (descent is stored
        // negative in stb's convention; take its magnitude).
        sm.ascent_px = static_cast<int>(std::round(impl_->ascent_u * sm.scale));
        sm.descent_px = static_cast<int>(std::round(-impl_->descent_u * sm.scale));
        sm.line_height = sm.ascent_px + sm.descent_px;
        return size_metrics_.emplace(px_size, sm).first->second;
    }

    // ---------------------------------------------------------------------------
    // Construction / destruction
    // ---------------------------------------------------------------------------

    FontAtlas::FontAtlas(const std::string& ttf_path, int default_preload_size_px, int atlas_width, int atlas_height)
        : impl_(std::make_unique<Impl>()),
          default_preload_size_(default_preload_size_px),
          atlas_w_(atlas_width),
          atlas_h_(atlas_height),
          atlas_(static_cast<size_t>(atlas_width) * static_cast<size_t>(atlas_height), 0u),
          sdf_atlas_(static_cast<size_t>(kSdfAtlasDim) * static_cast<size_t>(kSdfAtlasDim), 0u) {
        impl_->ttf_bytes = read_file_bytes(ttf_path);

        int offset = stbtt_GetFontOffsetForIndex(impl_->ttf_bytes.data(), 0);
        if (offset < 0) {
            throw std::runtime_error("FontAtlas: no font at index 0 in " + ttf_path);
        }
        if (!stbtt_InitFont(&impl_->font, impl_->ttf_bytes.data(), offset)) {
            throw std::runtime_error("FontAtlas: stbtt_InitFont failed for " + ttf_path);
        }

        const auto& bytes = impl_->ttf_bytes;
        FT_Error error = FT_Init_FreeType(&impl_->ft_library);
        if (!error)
            error = FT_New_Memory_Face(
                impl_->ft_library, bytes.data(), static_cast<FT_Long>(bytes.size()), 0, &impl_->ft_face);
        if (error || !impl_->ft_face->units_per_EM) {
            tc_log(TC_LOG_ERROR,
                   "[FontAtlas] FreeType cannot open scalable face in %s (error %d)",
                   ttf_path.c_str(),
                   error);
            throw std::runtime_error("FontAtlas: invalid scalable face in " + ttf_path);
        }
        hb_blob_t* blob = hb_blob_create(reinterpret_cast<const char*>(bytes.data()),
                                         static_cast<unsigned>(bytes.size()),
                                         HB_MEMORY_MODE_READONLY,
                                         nullptr,
                                         nullptr);
        hb_face_t* face = hb_face_create(blob, 0);
        hb_blob_destroy(blob);
        impl_->shaping_font = hb_font_create(face);
        hb_face_destroy(face);
        if (impl_->shaping_font == hb_font_get_empty() ||
            !hb_face_get_glyph_count(hb_font_get_face(impl_->shaping_font))) {
            tc_log(TC_LOG_ERROR, "[FontAtlas] HarfBuzz cannot open %s", ttf_path.c_str());
            throw std::runtime_error("FontAtlas: cannot create shaping font for " + ttf_path);
        }
        hb_ot_font_set_funcs(impl_->shaping_font);
        // Keep HarfBuzz positions in design units, independent of the hinted
        // FreeType slot used to fill each bitmap phase.
        const int upem = impl_->ft_face->units_per_EM;
        hb_font_set_scale(impl_->shaping_font, upem, upem);

        // Stash vmetrics in font-design units; every per-size resolution
        // scales from here.
        int line_gap_u = 0;
        stbtt_GetFontVMetrics(&impl_->font, &impl_->ascent_u, &impl_->descent_u, &line_gap_u);
        if (impl_->ascent_u <= impl_->descent_u) {
            tc_log(TC_LOG_ERROR, "[FontAtlas] invalid vertical metrics in %s", ttf_path.c_str());
            throw std::runtime_error("FontAtlas: invalid vertical metrics in " + ttf_path);
        }

        // Warm up the preload character set at the default bitmap size so
        // the first real frame of "typical" UI text doesn't stall on
        // rasterisation. Other bitmap sizes populate lazily.
        const float preload_px = static_cast<float>(default_preload_size_);
        size_t i = 0;
        std::string_view preload{kPreloadUtf8};
        while (i < preload.size()) {
            uint32_t cp = internal::utf8_decode(preload, i);
            ensure_glyph(cp, preload_px);
        }
        // SDF glyphs are shared by every SDF display size, so warm the same
        // common set once at the threshold. Without this, the first large
        // text draw pays the full SDF bake cost inside the render frame and
        // can appear a frame before later labels catch up.
        i = 0;
        while (i < preload.size()) {
            uint32_t cp = internal::utf8_decode(preload, i);
            ensure_glyph(cp, static_cast<float>(sdf_threshold_px_));
        }
        // Mark dirty so the first ensure_texture() uploads the preload.
        dirty_ = true;
        sdf_dirty_ = true;
    }

    FontAtlas::~FontAtlas() {
        // Best-effort GPU release. The device lifetime token prevents a late
        // atlas destructor from dereferencing a device that is already gone.
        release_gpu();
    }

    // ---------------------------------------------------------------------------
    // Glyph rasterisation
    // ---------------------------------------------------------------------------

    float FontAtlas::em_from_line_height(float line_height_px) const {
        return line_height_px * impl_->ft_face->units_per_EM / (impl_->ascent_u - impl_->descent_u);
    }

    float FontAtlas::line_height_from_em(float em_px) const {
        return em_px * (impl_->ascent_u - impl_->descent_u) / impl_->ft_face->units_per_EM;
    }

    FontAtlas::LineMetrics FontAtlas::screen_line_metrics(float line_px) const {
        if (!std::isfinite(line_px) || line_px <= 0.0f)
            return {};
        if (is_sdf_size(line_px)) {
            const auto& metrics = metrics_for_(sdf_reference_px_);
            const float scale = line_px / sdf_reference_px_;
            return {metrics.ascent_px * scale, metrics.descent_px * scale};
        }
        const float ascent = line_px * impl_->ascent_u / (impl_->ascent_u - impl_->descent_u);
        return {ascent, line_px - ascent};
    }

    FontAtlas::BitmapTextRun FontAtlas::layout_bitmap_text(std::string_view text_utf8, float em_px) const {
        BitmapTextRun run{};
        if (text_utf8.empty() || !std::isfinite(em_px) || em_px <= 0.0f)
            return run;
        if (text_utf8.size() > static_cast<size_t>(std::numeric_limits<int>::max())) {
            tc_log(TC_LOG_ERROR, "[FontAtlas] text exceeds HarfBuzz buffer length");
            return run;
        }
        std::unique_ptr<hb_buffer_t, decltype(&hb_buffer_destroy)> buffer(hb_buffer_create(), hb_buffer_destroy);
        const int length = static_cast<int>(text_utf8.size());
        hb_buffer_add_utf8(buffer.get(), text_utf8.data(), length, 0, length);
        hb_buffer_guess_segment_properties(buffer.get());
        hb_shape(impl_->shaping_font, buffer.get(), nullptr, 0);
        if (!hb_buffer_allocation_successful(buffer.get())) {
            tc_log(TC_LOG_ERROR, "[FontAtlas] HarfBuzz could not allocate a glyph run");
            throw std::bad_alloc();
        }

        unsigned count = 0;
        const auto* infos = hb_buffer_get_glyph_infos(buffer.get(), &count);
        const auto* positions = hb_buffer_get_glyph_positions(buffer.get(), nullptr);
        const double scale = static_cast<double>(em_px) / impl_->ft_face->units_per_EM;
        int64_t pen_x = 0, pen_y = 0;
        run.glyphs.reserve(count);
        for (unsigned i = 0; i < count; ++i) {
            run.glyphs.push_back({infos[i].codepoint,
                                  static_cast<float>((pen_x + positions[i].x_offset) * scale),
                                  static_cast<float>(-(pen_y + positions[i].y_offset) * scale)});
            pen_x += positions[i].x_advance;
            pen_y += positions[i].y_advance;
        }
        run.width_px = static_cast<float>(pen_x * scale);
        run.ascent_px = static_cast<float>(impl_->ascent_u * scale);
        run.height_px = line_height_from_em(em_px);
        return run;
    }

    FontAtlas::Size2f FontAtlas::measure_screen_text(std::string_view text_utf8, float size, FontSizeUnit unit) {
        if (text_utf8.empty() || !std::isfinite(size) || size <= 0.0f)
            return {};
        const float line_px = unit == FontSizeUnit::Em ? line_height_from_em(size) : size;
        if (is_sdf_size(line_px)) {
            ensure_glyphs(text_utf8, line_px);
            return {measure_text(text_utf8, line_px).width, screen_line_metrics(line_px).height()};
        }
        const float em_px = unit == FontSizeUnit::Em ? size : em_from_line_height(size);
        const auto run = layout_bitmap_text(text_utf8, em_px);
        return {run.width_px, run.height_px};
    }

    std::optional<FontAtlas::BitmapGlyph> FontAtlas::bitmap_glyph(uint32_t glyph_id, float em_px, unsigned phase) {
        // FreeType requests sizes in 26.6 units, with a 16-bit ppem limit.
        if (phase >= kBitmapPhaseCount || !std::isfinite(em_px) || em_px <= 0.0f || em_px > 65535.0f)
            return std::nullopt;
        const FT_F26Dot6 em = std::max(1L, std::lround(em_px * 64.0f));
        const uint64_t key =
            (static_cast<uint64_t>(glyph_id) << 32) | (static_cast<uint32_t>(em) * kBitmapPhaseCount + phase);
        const auto cached = impl_->screen_glyphs.find(key);
        if (cached != impl_->screen_glyphs.end())
            return cached->second;

        const auto face = impl_->ft_face;
        if (em != impl_->current_em) {
            const FT_Error error = FT_Set_Char_Size(face, 0, em, 72, 72);
            if (error) {
                tc_log(TC_LOG_ERROR, "[FontAtlas] FreeType rejected em size %.3f (error %d)", em_px, error);
                return std::nullopt;
            }
            impl_->current_em = em;
        }
        FT_Vector delta{static_cast<FT_Pos>(phase * (64 / kBitmapPhaseCount)), 0};
        FT_Set_Transform(face, nullptr, &delta);
        const FT_Error error =
            FT_Load_Glyph(face, glyph_id, FT_LOAD_NO_BITMAP | FT_LOAD_RENDER | FT_LOAD_TARGET_NORMAL);
        if (error) {
            tc_log(TC_LOG_ERROR,
                   "[FontAtlas] FreeType could not rasterise glyph %u at %.3f em px (error %d)",
                   glyph_id,
                   em_px,
                   error);
            return std::nullopt;
        }
        const FT_Bitmap& bitmap = face->glyph->bitmap;
        BitmapGlyph glyph{};
        if (bitmap.width && bitmap.rows) {
            if (bitmap.pixel_mode != FT_PIXEL_MODE_GRAY || bitmap.num_grays != 256) {
                tc_log(TC_LOG_ERROR, "[FontAtlas] expected 8-bit grayscale bitmap for glyph %u", glyph_id);
                return std::nullopt;
            }
            const int w = static_cast<int>(bitmap.width), h = static_cast<int>(bitmap.rows);
            const auto cell = pack_(w + 2, h + 2);
            if (cell.x < 0) {
                tc_log(TC_LOG_WARN, "[FontAtlas] atlas full for glyph %u at %.3f em px", glyph_id, em_px);
                return std::nullopt;
            }
            // Keep the complete ink rectangle, including bearings and marks
            // that extend beyond the font's logical line cell.
            const uint8_t* src = bitmap.buffer;
            if (bitmap.pitch < 0)
                src -= static_cast<ptrdiff_t>(h - 1) * bitmap.pitch;
            for (int row = 0; row < h; ++row) {
                std::memcpy(atlas_.data() + static_cast<size_t>(cell.y + row) * atlas_w_ + cell.x,
                            src + static_cast<ptrdiff_t>(row) * bitmap.pitch,
                            w);
            }
            glyph.u0 = static_cast<float>(cell.x) / atlas_w_;
            glyph.u1 = static_cast<float>(cell.x + w) / atlas_w_;
            glyph.v0 = static_cast<float>(cell.y) / atlas_h_;
            glyph.v1 = static_cast<float>(cell.y + h) / atlas_h_;
            glyph.width_px = static_cast<float>(w);
            glyph.height_px = static_cast<float>(h);
            glyph.offset_x_px = static_cast<float>(face->glyph->bitmap_left);
            glyph.offset_y_px = static_cast<float>(-face->glyph->bitmap_top);
            dirty_ = true;
        }
        impl_->screen_glyphs.emplace(key, glyph);
        return glyph;
    }

    FontAtlas::PackedCell FontAtlas::pack_(int cell_w, int cell_h) {
        if (cell_w > atlas_w_ || cell_h > atlas_h_)
            return {-1, -1};
        if (shelf_x_ + cell_w > atlas_w_) {
            shelf_y_ += shelf_h_;
            shelf_x_ = 0;
            shelf_h_ = 0;
        }
        if (shelf_y_ + cell_h > atlas_h_) {
            return {-1, -1};
        }
        PackedCell out{shelf_x_, shelf_y_};
        shelf_x_ += cell_w;
        shelf_h_ = std::max(shelf_h_, cell_h);
        return out;
    }

    bool FontAtlas::ensure_glyph(uint32_t codepoint, float display_px) {
        if (!impl_)
            return false;
        if (is_sdf_size(display_px)) {
            return ensure_sdf_glyph_(codepoint);
        }
        return ensure_bitmap_glyph_(codepoint, display_px);
    }

    bool FontAtlas::ensure_bitmap_glyph_(uint32_t codepoint, float display_px) {
        const int px_size = quantise_size_(display_px);
        const uint64_t key = make_key_(codepoint, px_size);
        if (glyphs_.count(key) != 0)
            return false;

        // Horizontal oversampling: rasterise the glyph at 2× its display
        // horizontal resolution and apply stb's box prefilter. At draw
        // time the bilinear sampler interpolates between these 2× texels,
        // which gives smoother transitions when the quad ends up at a
        // non-integer display position. ImGui default. Vertical stays at
        // 1× — doubling the atlas vertically is rarely worth it.
        //
        // Place the filtered bitmap using stb's matching oversample shift.
        constexpr int kOversampleX = 2;

        int glyph_idx = stbtt_FindGlyphIndex(&impl_->font, static_cast<int>(codepoint));
        if (glyph_idx == 0) {
            return false;
        }

        const SizeMetrics& sm = metrics_for_(px_size);
        const int gh_cell = sm.line_height;

        int x0 = 0, y0 = 0, x1 = 0, y1 = 0;
        stbtt_GetGlyphBitmapBox(&impl_->font, glyph_idx, sm.scale * kOversampleX, sm.scale, &x0, &y0, &x1, &y1);

        const int gw_over = x1 - x0;

        int adv_w = 0, lsb = 0;
        stbtt_GetGlyphHMetrics(&impl_->font, glyph_idx, &adv_w, &lsb);
        const float advance_px = adv_w * sm.scale;

        if (gw_over <= 0) {
            GlyphInfo g{};
            g.width_px = 0.0f;
            g.height_px = static_cast<float>(gh_cell);
            g.advance_px = advance_px;
            glyphs_[key] = g;
            return true;
        }

        constexpr int kPadding = 2;
        const int stored_w = gw_over + (kOversampleX - 1);
        const int cell_w = stored_w + kPadding;
        const int cell_h = gh_cell + kPadding;

        auto cell = pack_(cell_w, cell_h);
        if (cell.x < 0) {
            tc_log(TC_LOG_WARN, "[FontAtlas] Atlas full — cannot rasterise U+%04X at %d px", codepoint, px_size);
            return false;
        }

        const int dst_row0 = cell.y + sm.ascent_px + y0;
        const int gbh = y1 - y0;
        const int clip_top = std::max(0, -(dst_row0 - cell.y));
        const int dst_row0_clamped = dst_row0 + clip_top;
        const int rows_to_write = std::max(0, std::min(gbh - clip_top, (cell.y + gh_cell) - dst_row0_clamped));

        if (rows_to_write > 0) {
            uint8_t* dst = atlas_.data() + static_cast<size_t>(dst_row0_clamped) * atlas_w_ + cell.x;
            std::vector<uint8_t> scratch(static_cast<size_t>(gw_over) * gbh, 0);
            stbtt_MakeGlyphBitmapSubpixel(&impl_->font,
                                          scratch.data(),
                                          gw_over,
                                          gbh,
                                          gw_over,
                                          sm.scale * kOversampleX,
                                          sm.scale,
                                          0.0f,
                                          0.0f,
                                          glyph_idx);
            for (int r = 0; r < rows_to_write; ++r) {
                std::memcpy(dst + static_cast<size_t>(r) * atlas_w_,
                            scratch.data() + static_cast<size_t>(r + clip_top) * gw_over,
                            static_cast<size_t>(gw_over));
            }

            if (kOversampleX > 1) {
                stbtt__h_prefilter(dst, stored_w, rows_to_write, atlas_w_, kOversampleX);
            }
        }

        GlyphInfo g{};
        g.u0 = static_cast<float>(cell.x) / static_cast<float>(atlas_w_);
        g.v0 = static_cast<float>(cell.y) / static_cast<float>(atlas_h_);
        g.u1 = static_cast<float>(cell.x + stored_w) / static_cast<float>(atlas_w_);
        g.v1 = static_cast<float>(cell.y + gh_cell) / static_cast<float>(atlas_h_);
        g.width_px = static_cast<float>(stored_w) / static_cast<float>(kOversampleX);
        g.height_px = static_cast<float>(gh_cell);
        g.advance_px = advance_px;
        g.offset_x_px = static_cast<float>(x0) / kOversampleX + stbtt__oversample_shift(kOversampleX);
        glyphs_[key] = g;

        dirty_ = true;
        return true;
    }

    // ---------------------------------------------------------------------------
    // SDF glyph baking
    // ---------------------------------------------------------------------------

    FontAtlas::PackedCell FontAtlas::pack_sdf_(int cell_w, int cell_h) {
        if (sdf_shelf_x_ + cell_w > kSdfAtlasDim) {
            sdf_shelf_y_ += sdf_shelf_h_;
            sdf_shelf_x_ = 0;
            sdf_shelf_h_ = 0;
        }
        if (sdf_shelf_y_ + cell_h > kSdfAtlasDim) {
            return {-1, -1};
        }
        PackedCell out{sdf_shelf_x_, sdf_shelf_y_};
        sdf_shelf_x_ += cell_w;
        sdf_shelf_h_ = std::max(sdf_shelf_h_, cell_h);
        return out;
    }

    bool FontAtlas::ensure_sdf_glyph_(uint32_t codepoint) {
        // Already baked? SDF glyphs are keyed by codepoint only.
        if (sdf_glyphs_.count(codepoint) != 0)
            return false;

        int glyph_idx = stbtt_FindGlyphIndex(&impl_->font, static_cast<int>(codepoint));
        if (glyph_idx == 0)
            return false;

        const int ref = sdf_reference_px_;
        const SizeMetrics& sm = metrics_for_(ref);

        // Rasterise glyph at reference size, no oversampling — SDF doesn't
        // need horizontal sub-pixel smoothing; the distance field itself
        // provides the smoothness at render time.
        int x0 = 0, y0 = 0, x1 = 0, y1 = 0;
        stbtt_GetGlyphBitmapBox(&impl_->font, glyph_idx, sm.scale, sm.scale, &x0, &y0, &x1, &y1);

        const int gw = x1 - x0;
        const int gh = y1 - y0;

        int adv_w = 0, lsb = 0;
        stbtt_GetGlyphHMetrics(&impl_->font, glyph_idx, &adv_w, &lsb);
        const float advance_ref = adv_w * sm.scale;

        // Guard: no-ink glyphs — register with zero-size UVs and real advance.
        if (gw <= 0 || gh <= 0) {
            GlyphInfo g{};
            g.width_px = 0.0f;
            g.height_px = static_cast<float>(sm.line_height);
            g.advance_px = advance_ref;
            sdf_glyphs_[codepoint] = g;
            return true;
        }

        const int spread = sdf_spread_;
        // Padded bitmap: spread pixels on each side for the distance field.
        const int padded_w = gw + spread * 2;
        const int padded_h = gh + spread * 2;
        // Stored cell height = line_height + spread*2 for baseline alignment.
        const int cell_h = sm.line_height + spread * 2;
        const int cell_w = padded_w + 2; // +2 for minimal padding between glyphs

        auto cell = pack_sdf_(cell_w, cell_h);
        if (cell.x < 0) {
            tc_log(TC_LOG_WARN, "[FontAtlas] SDF atlas full — cannot bake U+%04X", codepoint);
            return false;
        }

        // Rasterise glyph bitmap into scratch (no oversampling).
        std::vector<uint8_t> scratch(static_cast<size_t>(gw) * gh, 0);
        stbtt_MakeGlyphBitmapSubpixel(
            &impl_->font, scratch.data(), gw, gh, gw, sm.scale, sm.scale, 0.0f, 0.0f, glyph_idx);

        // Build padded bitmap: glyph at (spread, spread), surrounded by
        // `spread` pixels on all four sides. y0 is accounted for when
        // placing the padded bitmap in the atlas cell, not here.
        std::vector<uint8_t> padded(static_cast<size_t>(padded_w) * padded_h, 0);
        for (int r = 0; r < gh; ++r) {
            std::memcpy(padded.data() + (r + spread) * padded_w + spread, scratch.data() + r * gw, gw);
        }

        // Compute signed distance field.
        std::vector<uint8_t> sdf(static_cast<size_t>(padded_w) * padded_h, 0);
        compute_sdf_(padded.data(), padded_w, padded_h, sdf.data(), padded_w);

        // Place padded bitmap in the atlas cell. The glyph sits at (spread,
        // spread) within the padded buffer. The glyph top should land at
        // atlas row (ascent_px + y0) relative to the baseline row, which is
        // at (spread + ascent_px) from the cell top. So padded-top goes to:
        //   cell.y + spread + ascent_px + y0 - spread = cell.y + ascent_px + y0
        const int dst_row0 = cell.y + sm.ascent_px + y0;
        const int clip_top = std::max(0, -(dst_row0 - cell.y));
        const int dst_row0_clamped = dst_row0 + clip_top;
        const int rows_to_write = std::max(0, std::min(padded_h - clip_top, (cell.y + cell_h) - dst_row0_clamped));

        if (rows_to_write > 0) {
            uint8_t* dst = sdf_atlas_.data() + static_cast<size_t>(dst_row0_clamped) * kSdfAtlasDim + cell.x;
            for (int r = 0; r < rows_to_write; ++r) {
                std::memcpy(dst + static_cast<size_t>(r) * kSdfAtlasDim,
                            sdf.data() + static_cast<size_t>(r + clip_top) * padded_w,
                            static_cast<size_t>(padded_w));
            }
        }

        // Stored region covers the padded glyph (spread on each side).
        const int stored_w = padded_w;
        const int stored_h = cell_h; // line_height + spread*2 for baseline alignment

        GlyphInfo g{};
        g.u0 = static_cast<float>(cell.x) / static_cast<float>(kSdfAtlasDim);
        g.v0 = static_cast<float>(cell.y) / static_cast<float>(kSdfAtlasDim);
        g.u1 = static_cast<float>(cell.x + stored_w) / static_cast<float>(kSdfAtlasDim);
        g.v1 = static_cast<float>(cell.y + stored_h) / static_cast<float>(kSdfAtlasDim);
        // get_glyph() scales all reference-size metrics to display pixels.
        g.width_px = static_cast<float>(stored_w);
        g.height_px = static_cast<float>(stored_h);
        g.advance_px = advance_ref;
        g.offset_x_px = static_cast<float>(x0 - spread);
        sdf_glyphs_[codepoint] = g;

        sdf_dirty_ = true;
        return true;
    }

    void FontAtlas::compute_sdf_(const uint8_t* bitmap, int w, int h, uint8_t* sdf, int sdf_stride) {
        // Euclidean signed distance field via two-pass dead-reckoning
        // distance transform (8SSEDT variant).
        //
        // Step 1: unsigned distance to nearest edge.
        // Step 2: apply sign based on inside/outside.
        // Step 3: encode to R8.

        const int n = w * h;
        std::vector<float> dist(n);

        const int spread = sdf_spread_;
        const float kMax = static_cast<float>(spread);

        // Initialise unsigned distances: 0 at edges, kMax elsewhere.
        // An edge is where a pixel and its neighbour differ (inside↔outside).
        for (int y = 0; y < h; ++y) {
            for (int x = 0; x < w; ++x) {
                const int idx = y * w + x;
                const bool inside = (bitmap[idx] > 127);
                // Check 4-neighbours for a sign change → this pixel is an edge.
                bool edge = false;
                if (x > 0 && inside != (bitmap[idx - 1] > 127))
                    edge = true;
                if (x < w - 1 && inside != (bitmap[idx + 1] > 127))
                    edge = true;
                if (y > 0 && inside != (bitmap[idx - w] > 127))
                    edge = true;
                if (y < h - 1 && inside != (bitmap[idx + w] > 127))
                    edge = true;
                dist[idx] = edge ? 0.0f : kMax;
            }
        }

        // Pass 1: top-left → bottom-right.
        for (int y = 0; y < h; ++y) {
            for (int x = 0; x < w; ++x) {
                const int idx = y * w + x;
                float d = dist[idx];

                if (x > 0) {
                    d = std::min(d, dist[idx - 1] + 1.0f);
                }
                if (y > 0) {
                    d = std::min(d, dist[idx - w] + 1.0f);
                    if (x > 0) {
                        d = std::min(d, dist[idx - w - 1] + 1.414f);
                    }
                    if (x < w - 1) {
                        d = std::min(d, dist[idx - w + 1] + 1.414f);
                    }
                }
                dist[idx] = d;
            }
        }

        // Pass 2: bottom-right → top-left.
        for (int y = h - 1; y >= 0; --y) {
            for (int x = w - 1; x >= 0; --x) {
                const int idx = y * w + x;
                float d = dist[idx];

                if (x < w - 1) {
                    d = std::min(d, dist[idx + 1] + 1.0f);
                }
                if (y < h - 1) {
                    d = std::min(d, dist[idx + w] + 1.0f);
                    if (x > 0) {
                        d = std::min(d, dist[idx + w - 1] + 1.414f);
                    }
                    if (x < w - 1) {
                        d = std::min(d, dist[idx + w + 1] + 1.414f);
                    }
                }
                dist[idx] = d;
            }
        }

        // Apply sign and encode to R8.
        for (int y = 0; y < h; ++y) {
            for (int x = 0; x < w; ++x) {
                const int idx = y * w + x;
                float sd = dist[idx]; // unsigned distance in [0, spread]
                if (bitmap[idx] <= 127) {
                    sd = -sd; // outside → negative
                }
                float v = 0.5f + 0.5f * (sd / static_cast<float>(spread));
                if (v < 0.0f)
                    v = 0.0f;
                if (v > 1.0f)
                    v = 1.0f;
                sdf[static_cast<size_t>(y) * sdf_stride + x] = static_cast<uint8_t>(v * 255.0f);
            }
        }
    }

    // ---------------------------------------------------------------------------
    // SDF GPU upload
    // ---------------------------------------------------------------------------

    void FontAtlas::sync_sdf_gpu_(RenderContext2* ctx) {
        if (!ctx)
            return;
        IRenderDevice& device = ctx->device();
        ensure_gpu_device_(device);
        if (sdf_gpu_texture_.id == 0)
            return;
        device.upload_texture(sdf_gpu_texture_, std::span<const uint8_t>(sdf_atlas_.data(), sdf_atlas_.size()));
        sdf_dirty_ = false;
    }

    TextureHandle FontAtlas::sdf_atlas_texture(RenderContext2* ctx) {
        if (!ctx)
            return TextureHandle{};

        IRenderDevice& device = ctx->device();
        ensure_gpu_device_(device);

        if (sdf_gpu_texture_.id == 0) {
            TextureDesc desc{};
            desc.width = static_cast<uint32_t>(kSdfAtlasDim);
            desc.height = static_cast<uint32_t>(kSdfAtlasDim);
            desc.mip_levels = 1;
            desc.sample_count = 1;
            desc.format = PixelFormat::R8_UNorm;
            desc.usage = TextureUsage::Sampled | TextureUsage::CopyDst;
            sdf_gpu_texture_ = device.create_texture(desc);
            if (sdf_gpu_texture_.id != 0) {
                device.upload_texture(sdf_gpu_texture_, std::span<const uint8_t>(sdf_atlas_.data(), sdf_atlas_.size()));
                sdf_dirty_ = false;
            } else {
                tc_log(TC_LOG_ERROR, "[FontAtlas] failed to create SDF atlas texture");
            }
        } else if (sdf_dirty_) {
            sync_sdf_gpu_(ctx);
        }
        return sdf_gpu_texture_;
    }

    void FontAtlas::ensure_glyphs(std::string_view text_utf8, float display_px, RenderContext2* ctx) {
        bool added_any = false;
        size_t i = 0;
        while (i < text_utf8.size()) {
            uint32_t cp = internal::utf8_decode(text_utf8, i);
            if (ensure_glyph(cp, display_px)) {
                added_any = true;
            }
        }
        if (added_any && ctx != nullptr) {
            if (is_sdf_size(display_px)) {
                sync_sdf_gpu_(ctx);
            } else {
                sync_gpu_(ctx);
            }
        }
    }

    // ---------------------------------------------------------------------------
    // Measurement
    // ---------------------------------------------------------------------------

    FontAtlas::Size2f FontAtlas::measure_text(std::string_view text_utf8, float display_px) const {
        Size2f out{};
        if (text_utf8.empty())
            return out;

        if (is_sdf_size(display_px)) {
            const float s = display_px / static_cast<float>(sdf_reference_px_);
            size_t i = 0;
            float width = 0.0f;
            while (i < text_utf8.size()) {
                uint32_t cp = internal::utf8_decode(text_utf8, i);
                auto it = sdf_glyphs_.find(cp);
                if (it != sdf_glyphs_.end()) {
                    width += it->second.advance_px * s;
                }
            }
            out.width = width;
            out.height = display_px;
            return out;
        }

        const int px_size = quantise_size_(display_px);
        size_t i = 0;
        float width = 0.0f;
        while (i < text_utf8.size()) {
            uint32_t cp = internal::utf8_decode(text_utf8, i);
            auto it = glyphs_.find(make_key_(cp, px_size));
            if (it != glyphs_.end()) {
                width += it->second.advance_px;
            }
        }
        out.width = width;
        out.height = display_px;
        return out;
    }

    std::optional<FontAtlas::GlyphInfo> FontAtlas::get_glyph(uint32_t codepoint, float display_px) const {
        if (is_sdf_size(display_px)) {
            auto it = sdf_glyphs_.find(codepoint);
            if (it == sdf_glyphs_.end())
                return std::nullopt;

            // SDF glyphs are stored with reference-size metrics. Scale to
            // display pixels on return. The caller must NOT further scale.
            GlyphInfo scaled;
            const float s = display_px / static_cast<float>(sdf_reference_px_);
            const auto& g = it->second;
            scaled.u0 = g.u0;
            scaled.v0 = g.v0;
            scaled.u1 = g.u1;
            scaled.v1 = g.v1;
            scaled.width_px = g.width_px * s;
            scaled.height_px = g.height_px * s;
            scaled.advance_px = g.advance_px * s;
            scaled.offset_x_px = g.offset_x_px * s;
            return scaled;
        }

        const int px_size = quantise_size_(display_px);
        auto it = glyphs_.find(make_key_(codepoint, px_size));
        if (it == glyphs_.end())
            return std::nullopt;
        return it->second;
    }

    // ---------------------------------------------------------------------------
    // Size-aware metrics
    // ---------------------------------------------------------------------------

    int FontAtlas::ascent_px(float display_px) const {
        return metrics_for_(quantise_size_(display_px)).ascent_px;
    }

    int FontAtlas::descent_px(float display_px) const {
        return metrics_for_(quantise_size_(display_px)).descent_px;
    }

    int FontAtlas::line_height_px(float display_px) const {
        return metrics_for_(quantise_size_(display_px)).line_height;
    }

    // ---------------------------------------------------------------------------
    // GPU upload
    // ---------------------------------------------------------------------------

    void FontAtlas::ensure_gpu_device_(IRenderDevice& device) {
        if (gpu_device_ == &device && !gpu_device_lifetime_.expired()) {
            return;
        }

        // Bitmap and SDF handles are one device-owned cache. A device switch
        // invalidates both representations before either upload path can use a
        // numerically identical handle minted by another device.
        release_gpu();
        gpu_device_ = &device;
        gpu_device_lifetime_ = device.lifetime_token();
    }

    TextureHandle FontAtlas::ensure_texture(RenderContext2* ctx) {
        if (!ctx)
            return TextureHandle{};

        const bool profile = tc_profiler_enabled();

        IRenderDevice& device = ctx->device();
        if (gpu_device_ != &device || gpu_device_lifetime_.expired()) {
            if (profile)
                tc_profiler_begin_section("atlas.device_swap");
            ensure_gpu_device_(device);
            if (profile)
                tc_profiler_end_section();
        }

        if (gpu_texture_.id == 0) {
            if (profile)
                tc_profiler_begin_section("atlas.create+upload");
            TextureDesc desc{};
            desc.width = static_cast<uint32_t>(atlas_w_);
            desc.height = static_cast<uint32_t>(atlas_h_);
            desc.mip_levels = 1;
            desc.sample_count = 1;
            desc.format = PixelFormat::R8_UNorm;
            desc.usage = TextureUsage::Sampled | TextureUsage::CopyDst;
            gpu_texture_ = device.create_texture(desc);
            if (gpu_texture_.id != 0) {
                device.upload_texture(gpu_texture_, std::span<const uint8_t>(atlas_.data(), atlas_.size()));
                dirty_ = false;
            } else {
                tc_log(TC_LOG_ERROR, "[FontAtlas] failed to create bitmap atlas texture");
            }
            if (profile)
                tc_profiler_end_section();
        } else if (dirty_) {
            if (profile)
                tc_profiler_begin_section("atlas.reupload");
            sync_gpu_(ctx);
            if (profile)
                tc_profiler_end_section();
        }
        return gpu_texture_;
    }

    void FontAtlas::sync_gpu_(RenderContext2* ctx) {
        if (!ctx)
            return;
        IRenderDevice& device = ctx->device();
        ensure_gpu_device_(device);
        if (gpu_texture_.id == 0)
            return;
        device.upload_texture(gpu_texture_, std::span<const uint8_t>(atlas_.data(), atlas_.size()));
        dirty_ = false;
    }

    void FontAtlas::release_gpu() {
        // Isolated devices are just as valid as the process-global interop
        // device. The weak token lets us release their resources while they
        // are alive and safely drop stale handles after they are destroyed.
        if (gpu_device_ != nullptr) {
            const std::shared_ptr<const void> lifetime = gpu_device_lifetime_.lock();
            if (lifetime) {
                if (gpu_texture_.id != 0) {
                    gpu_device_->destroy(gpu_texture_);
                }
                if (sdf_gpu_texture_.id != 0) {
                    gpu_device_->destroy(sdf_gpu_texture_);
                }
            }
        }
        gpu_texture_ = TextureHandle{};
        sdf_gpu_texture_ = TextureHandle{};
        gpu_device_ = nullptr;
        gpu_device_lifetime_.reset();
        // CPU atlas + glyphs stay — the caller may re-ensure on a new
        // context without paying the rasterisation cost again.
        dirty_ = true;
        sdf_dirty_ = true;
    }

} // namespace tgfx
