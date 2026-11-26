#pragma once

#include "tgfx2/draw_list2d.hpp"
#include "tgfx2/font_atlas.hpp"
#include "tgfx2/text2d_renderer.hpp"

namespace tgfx::internal {

    // Both sizes are in physical pixels. Keeping the legacy size alongside em
    // also gives bitmap and SDF the same threshold when callers switch units.
    struct ScreenFontSize {
        float em_px;
        float line_px;

        ScreenFontSize(const FontAtlas& font, float size, FontSizeUnit unit)
            : em_px(unit == FontSizeUnit::Em ? size : font.em_from_line_height(size)),
              line_px(unit == FontSizeUnit::Em ? font.line_height_from_em(size) : size) {}
    };

    // raster_to_screen places the anchor and maps raster-pixel vectors to
    // screen-pixel vectors. Both drawing paths upload the atlas after this call.
    std::vector<Text2DVertex> screen_text_vertices(FontAtlas& font,
                                                   std::string_view text,
                                                   ScreenFontSize size,
                                                   const termin::Affine2f& raster_to_screen,
                                                   TextAnchor2D anchor,
                                                   TextVerticalAnchor2D vertical_anchor,
                                                   bool snap_sdf_origin);

} // namespace tgfx::internal
