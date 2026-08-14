#pragma once

#include <cstdint>
#include <string>

namespace tgfx {
    class GraphicsHost;
    class IRenderDevice;
    struct TextureHandle;
} // namespace tgfx

namespace termin::web {

    bool render_visual_scene_example(tgfx::IRenderDevice& device,
                                     tgfx::GraphicsHost& graphics_host,
                                     tgfx::TextureHandle presentation_texture,
                                     std::uint32_t width,
                                     std::uint32_t height,
                                     std::string& error);

} // namespace termin::web
