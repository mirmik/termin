#pragma once

#include <cstdint>
#include <string>

namespace tgfx {
    class GraphicsHost;
    class WebGpuRenderDevice;
} // namespace tgfx

namespace termin::web {

    bool render_visual_scene_example(tgfx::WebGpuRenderDevice& device,
                                     tgfx::GraphicsHost& graphics_host,
                                     std::uint32_t width,
                                     std::uint32_t height,
                                     std::string& error);

} // namespace termin::web
