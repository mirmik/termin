// SDF font atlas smoke test — exercises FontAtlas bitmap/SDF paths without GPU.
// Run with: ./tgfx2_sdf_test
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdio>

#include "tgfx2/font_atlas.hpp"

#ifndef TGFX2_TEST_FONT_PATH
#error "TGFX2_TEST_FONT_PATH must point at a deterministic test TTF"
#endif

namespace {

    int failures = 0;

    void check(bool condition, const char* message) {
        if (!condition) {
            fprintf(stderr, "FAIL: %s\n", message);
            ++failures;
        }
    }

    bool
    atlas_region_has_signal(const uint8_t* atlas, int atlas_w, int atlas_h, const tgfx::FontAtlas::GlyphInfo& glyph) {
        int x0 = std::clamp(static_cast<int>(std::floor(glyph.u0 * atlas_w)), 0, atlas_w);
        int y0 = std::clamp(static_cast<int>(std::floor(glyph.v0 * atlas_h)), 0, atlas_h);
        int x1 = std::clamp(static_cast<int>(std::ceil(glyph.u1 * atlas_w)), 0, atlas_w);
        int y1 = std::clamp(static_cast<int>(std::ceil(glyph.v1 * atlas_h)), 0, atlas_h);
        if (x1 <= x0 || y1 <= y0) {
            return false;
        }
        for (int y = y0; y < y1; ++y) {
            for (int x = x0; x < x1; ++x) {
                if (atlas[static_cast<size_t>(y) * atlas_w + x] != 0) {
                    return true;
                }
            }
        }
        return false;
    }

    void check_glyph(const tgfx::FontAtlas::GlyphInfo& glyph, const char* label) {
        check(glyph.u0 >= 0.0f && glyph.u0 <= glyph.u1 && glyph.u1 <= 1.0f, label);
        check(glyph.v0 >= 0.0f && glyph.v0 <= glyph.v1 && glyph.v1 <= 1.0f, label);
        check(glyph.width_px > 0.0f, label);
        check(glyph.height_px > 0.0f, label);
        check(glyph.advance_px > 0.0f, label);
    }

    void check_glyph_offsets(tgfx::FontAtlas& font, float size, float expected_en, float expected_j) {
        // U+043D (Cyrillic small en) has a positive ink bearing in Droid Sans.
        // Lowercase j overhangs the pen to the left.
        const char* run = "\xd0\xbdj\xd0\xbdj ";
        font.ensure_glyphs(run, size);
        const auto en = font.get_glyph(0x043d, size);
        const auto j = font.get_glyph('j', size);
        const auto space = font.get_glyph(' ', size);
        check(en && j && space, "spacing probe glyphs should be present");
        if (!en || !j || !space)
            return;
        check(en->offset_x_px == expected_en, "en quad should retain its horizontal offset");
        check(j->offset_x_px == expected_j, "j quad should retain its left overhang");
        check(space->width_px == 0 && space->advance_px > 0, "space should advance without ink");
        const float expected_width = 2 * (en->advance_px + j->advance_px) + space->advance_px;
        check(std::abs(font.measure_text(run, size).width - expected_width) < 1e-4f,
              "repeated glyphs should advance independently of their quad offsets");
    }

} // namespace

int main() {
    // Load font.
    const char* font_path = TGFX2_TEST_FONT_PATH;
    tgfx::FontAtlas font(font_path, 14);
    // Bitmap box origins are 2 and -1 oversampled texels at 14 px;
    // the 2x box prefilter shifts the quad by another -0.25 display px.
    check_glyph_offsets(font, 14.0f, 0.75f, -0.75f);
    // At the 64 px SDF reference size, ink begins at +4 and -2.
    // The quad also includes spread texels to the left of that ink.
    const float spread = static_cast<float>(font.sdf_spread());
    check_glyph_offsets(font, 64.0f, 4 - spread, -2 - spread);
    check_glyph_offsets(font, 48.0f, 0.75f * (4 - spread), 0.75f * (-2 - spread));
    printf("Font loaded: %s\n", font_path);
    printf("SDF config: enabled=%d threshold=%d ref=%d spread=%d\n",
           font.sdf_enabled(),
           font.sdf_threshold_px(),
           font.sdf_reference_px(),
           font.sdf_spread());

    // Test string — covers ASCII printable, some CJK, symbols.
    const char* test_str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789 "
                           "!@#$%^&*() []{}|;:',.<>?/`~"
                           "\xe2\x96\xb6\xe2\x96\xbc\xe2\x86\x90\xe2\x86\x92"; // ▶▼←→

    // Exercise bitmap path (below threshold).
    printf("\n--- Bitmap path ---\n");
    for (float sz : {8.0f, 10.0f, 12.0f, 14.0f, 16.0f, 18.0f, 24.0f, 28.0f, 32.0f}) {
        font.ensure_glyphs(test_str, sz);
        auto m = font.measure_text(test_str, sz);
        printf("  size=%.0f  measure=(%.1f, %.1f)  sdf=%d\n", sz, m.width, m.height, font.is_sdf_size(sz));
        check(!font.is_sdf_size(sz), "bitmap path should stay below SDF threshold");
        check(m.width > 0.0f, "bitmap text measure width should be positive");
        check(m.height == sz, "bitmap text measure height should match requested size");
    }
    check(font.cpu_atlas_data() != nullptr, "bitmap CPU atlas should be allocated");
    check(font.atlas_width() > 0, "bitmap atlas width should be positive");
    check(font.atlas_height() > 0, "bitmap atlas height should be positive");
    auto bitmap_a = font.get_glyph('A', 14.0f);
    check(bitmap_a.has_value(), "bitmap glyph A should be present at 14px");
    if (bitmap_a) {
        check_glyph(*bitmap_a, "bitmap glyph A metrics/UV should be valid");
        check(atlas_region_has_signal(font.cpu_atlas_data(), font.atlas_width(), font.atlas_height(), *bitmap_a),
              "bitmap glyph A atlas region should contain nonzero pixels");
    }

    // Exercise SDF path (above threshold).
    printf("\n--- SDF path ---\n");
    for (float sz : {48.0f, 64.0f}) {
        font.ensure_glyphs(test_str, sz);
        auto m = font.measure_text(test_str, sz);
        printf("  size=%.0f  measure=(%.1f, %.1f)  sdf=%d\n", sz, m.width, m.height, font.is_sdf_size(sz));
        check(font.is_sdf_size(sz), "SDF path should be active at and above threshold");
        check(m.width > 0.0f, "SDF text measure width should be positive");
        check(m.height == sz, "SDF text measure height should match requested size");
    }
    check(font.sdf_atlas_data() != nullptr, "SDF CPU atlas should be allocated");
    auto sdf_a = font.get_glyph('A', 48.0f);
    check(sdf_a.has_value(), "SDF glyph A should be present at 48px");
    if (sdf_a) {
        check_glyph(*sdf_a, "SDF glyph A metrics/UV should be valid");
        check(atlas_region_has_signal(
                  font.sdf_atlas_data(), tgfx::FontAtlas::kSdfAtlasDim, tgfx::FontAtlas::kSdfAtlasDim, *sdf_a),
              "SDF glyph A atlas region should contain nonzero pixels");
    }

    // Verify individual glyph lookup works for SDF.
    printf("\n--- Glyph lookup ---\n");
    uint32_t test_cps[] = {'A', 'a', '0', '@', 'g', 'W', 0};
    for (int i = 0; test_cps[i]; ++i) {
        for (float sz : {14.0f, 28.0f, 48.0f}) {
            auto gi = font.get_glyph(test_cps[i], sz);
            if (gi) {
                printf("  U+%04X size=%.0f sdf=%d uv=(%.3f,%.3f)-(%.3f,%.3f) "
                       "size=(%.1f,%.1f) adv=%.1f\n",
                       test_cps[i],
                       sz,
                       font.is_sdf_size(sz),
                       gi->u0,
                       gi->v0,
                       gi->u1,
                       gi->v1,
                       gi->width_px,
                       gi->height_px,
                       gi->advance_px);
                check_glyph(*gi, "glyph lookup metrics/UV should be valid");
            } else {
                printf("  U+%04X size=%.0f — MISSING\n", test_cps[i], sz);
                check(false, "expected glyph should be present");
            }
        }
    }

    // Preload stress: many codepoints at SDF size.
    printf("\n--- SDF preload stress ---\n");
    const char* stress_str = " !\"#$%&'()*+,-./0123456789:;<=>?@"
                             "ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`"
                             "abcdefghijklmnopqrstuvwxyz{|}~"
                             "\xe2\x96\xb6\xe2\x96\xbc\xe2\x96\xb2\xe2\x97\x80"  // ▶▼▲◀
                             "\xe2\x96\xa0\xe2\x96\xa1\xe2\x96\xa3\xe2\x96\xab"  // ■□▣▫
                             "\xe2\x97\x8b\xe2\x97\x8f\xe2\x97\x88\xe2\x97\x86"  // ○●◈◆
                             "\xe2\x80\xa2\xe2\x80\xa3\xe2\x97\xa6"              // •‣◦
                             "\xe2\x9c\x93\xe2\x9c\x97\xe2\x9c\x95"              // ✓✗✕
                             "\xe2\x86\x90\xe2\x86\x92\xe2\x86\x91\xe2\x86\x93"; // ←→↑↓
    font.ensure_glyphs(stress_str, 48.0f);
    auto m = font.measure_text(stress_str, 48.0f);
    printf("  Stress string measure at 48px: %.1f x %.1f\n", m.width, m.height);
    check(m.width > 0.0f, "stress string measure width should be positive");
    check(m.height == 48.0f, "stress string measure height should match requested size");

    if (failures != 0) {
        fprintf(stderr, "\nSDF atlas test failed with %d assertion(s).\n", failures);
        return 1;
    }
    printf("\nTest completed successfully.\n");
    return 0;
}
