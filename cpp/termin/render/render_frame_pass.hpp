#pragma once

#include <unordered_map>
#include <vector>

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
 * FBO map type: resource name -> framebuffer handle.
 */
using FBOMap = std::unordered_map<std::string, FramebufferHandle*>;

/**
 * Base class for render passes that draw to framebuffers.
 *
 * Subclasses implement execute() to perform actual rendering.
 * The frame graph scheduler calls execute() with all dependencies resolved.
 */
class RenderFramePass : public FramePass {
public:
    using FramePass::FramePass;

    virtual ~RenderFramePass() = default;

    /**
     * Execute the render pass.
     *
     * @param graphics Graphics backend for GPU operations
     * @param reads_fbos Map of input resource names to FBOs
     * @param writes_fbos Map of output resource names to FBOs
     * @param rect Viewport rectangle (x, y, width, height)
     * @param scene Current scene (opaque pointer for now)
     * @param camera Active camera (opaque pointer for now)
     * @param context_key Key for VAO/shader caching
     * @param lights Pre-computed light list (optional)
     */
    virtual void execute(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        void* scene,
        void* camera,
        int64_t context_key,
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
};

using RenderFramePassPtr = std::unique_ptr<RenderFramePass>;

} // namespace termin
