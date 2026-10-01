#pragma once

namespace tgfx {
    class IRenderDevice;
}

// Reuses the caller's fullscreen triangle vertex shader.
bool render_sampler_state_smoke(tgfx::IRenderDevice& device, const char* vertex_source);
