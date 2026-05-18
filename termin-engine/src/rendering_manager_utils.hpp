#pragma once

#include <cstdint>

#include <tgfx2/enums.hpp>

extern "C" {
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

namespace termin {

inline tgfx::PixelFormat render_target_format_to_tgfx2(tc_texture_format fmt) {
    switch (fmt) {
        case TC_TEXTURE_RGBA8: return tgfx::PixelFormat::RGBA8_UNorm;
        case TC_TEXTURE_RGB8: return tgfx::PixelFormat::RGB8_UNorm;
        case TC_TEXTURE_RG8: return tgfx::PixelFormat::RG8_UNorm;
        case TC_TEXTURE_R8: return tgfx::PixelFormat::R8_UNorm;
        case TC_TEXTURE_RGBA16F: return tgfx::PixelFormat::RGBA16F;
        case TC_TEXTURE_RGB16F: return tgfx::PixelFormat::RGBA16F;
        case TC_TEXTURE_R16F: return tgfx::PixelFormat::R16F;
        case TC_TEXTURE_R32F: return tgfx::PixelFormat::R32F;
        case TC_TEXTURE_DEPTH24: return tgfx::PixelFormat::D24_UNorm;
        case TC_TEXTURE_DEPTH32F: return tgfx::PixelFormat::D32F;
    }
    return tgfx::PixelFormat::RGBA8_UNorm;
}

inline uint64_t viewport_key(tc_viewport_handle h) {
    return (static_cast<uint64_t>(h.index) << 32) | h.generation;
}

} // namespace termin
