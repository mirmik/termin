#pragma once

#include "render/tc_display_pool.h"
#include "render/termin_display_api.h"

namespace tgfx {
    class IRenderDevice;
}

namespace termin {

    // Create a display together with its exclusively owned backend-neutral
    // offscreen texture surface. On failure no display or surface remains alive.
    TERMIN_DISPLAY_API tc_display_handle create_offscreen_display(tgfx::IRenderDevice* device,
                                                                  int width,
                                                                  int height,
                                                                  const char* name);

} // namespace termin
