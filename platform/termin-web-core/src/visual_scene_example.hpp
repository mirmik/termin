#pragma once

#include <cstdint>
#include <string>

namespace tgfx {
    class GraphicsHost;
    struct TextureHandle;
} // namespace tgfx

namespace termin::web {

    bool render_visual_scene_example(tgfx::GraphicsHost& graphics_host,
                                     tgfx::TextureHandle presentation_texture,
                                     std::uint32_t width,
                                     std::uint32_t height,
                                     std::string& error);

} // namespace termin::web
