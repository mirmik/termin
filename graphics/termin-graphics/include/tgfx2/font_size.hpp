#pragma once

#include <cstdint>

namespace tgfx {

    enum class FontSizeUnit : std::uint8_t {
        // Distance between the font's ascender and descender, in pixels.
        LineHeight,
        // Typographic em, in pixels, as used by desktop UI toolkits.
        Em,
    };

} // namespace tgfx
