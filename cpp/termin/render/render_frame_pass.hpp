#pragma once

#include <unordered_map>
#include <vector>
#include <functional>

#include "termin/render/frame_pass.hpp"

#include "termin/render/handles.hpp"
#include "termin/render/resource_spec.hpp"

namespace termin {

// Forward declarations
class GraphicsBackend;
class Scene;
class Camera;
class Light;

/**
 * Viewport rectangle in pixels.
 */
struct Rect4i {
    int x = 0;
    int y = 0;
    int width = 0;
    int height = 0;
};

/**
 * Resource map type: resource name -> framegraph resource.
 * Can contain FramebufferHandle, ShadowMapArrayResource, etc.
 */
using ResourceMap = std::unordered_map<std::string, FrameGraphResource*>;

// Legacy alias for backwards compatibility
using FBOMap = ResourceMap;

/**
 * Callbacks for frame debugger integration.
 * Language-agnostic interface - Python/C# bindings wrap this.
 */
struct FrameDebuggerCallbacks {
    void* user_data = nullptr;

    // Called to blit framebuffer content to debugger window
    void (*blit_from_pass)(
        void* user_data,
        FramebufferHandle* fb,
        GraphicsBackend* graphics,
        int width,
        int height
    ) = nullptr;

    // Called to capture depth buffer (optional)
    void (*capture_depth)(
        void* user_data,
        FramebufferHandle* fb,
        int width,
        int height,
        float* out_data
    ) = nullptr;

    // Called on error (optional)
    void (*on_error)(
        void* user_data,
        const char* message
    ) = nullptr;

    bool is_set() const { return blit_from_pass != nullptr; }
};

/**
 * Base class for render passes that draw to framebuffers.
 *
 * Subclasses implement execute() to perform actual rendering.
 * The frame graph scheduler calls execute() with all dependencies resolved.
 */
class RenderFramePass : public FramePass {
public:
    // C++ callback-based debugger interface
    FrameDebuggerCallbacks debugger_callbacks;

    using FramePass::FramePass;

    virtual ~RenderFramePass() = default;

    void set_debugger_callbacks(const FrameDebuggerCallbacks& callbacks) {
        debugger_callbacks = callbacks;
    }

    void clear_debugger_callbacks() {
        debugger_callbacks = {};
    }

    bool has_debugger() const {
        return debugger_callbacks.is_set();
    }

    /**
     * Execute the render pass.
     *
     * @param graphics Graphics backend for GPU operations
     * @param reads_fbos Map of input resource names to FBOs
     * @param writes_fbos Map of output resource names to FBOs
     * @param rect Viewport rectangle (x, y, width, height)
     * @param scene Current scene (opaque pointer for now)
     * @param camera Active camera (opaque pointer for now)
     * @param lights Pre-computed light list (optional)
     */
    virtual void execute(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        void* scene,
        void* camera,
        const std::vector<Light*>* lights = nullptr
    ) = 0;

    /**
     * Returns resource specifications for this pass.
     *
     * Passes can declare fixed sizes, clear colors, formats, etc.
     * Default: no special requirements.
     */
    virtual std::vector<ResourceSpec> get_resource_specs() const {
        return {};
    }

    /**
     * Clean up pass resources (FBOs, shaders, etc).
     *
     * Called when switching pipelines to release cached GL resources.
     * Subclasses should override to release their cached resources.
     */
    virtual void destroy() {}
};

using RenderFramePassPtr = std::unique_ptr<RenderFramePass>;

} // namespace termin
