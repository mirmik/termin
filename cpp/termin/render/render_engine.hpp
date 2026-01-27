#pragma once

#include <string>
#include <unordered_map>
#include <vector>

#include "termin/render/graphics_backend.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/lighting/light.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/tc_scene_ref.hpp"

extern "C" {
#include "render/tc_frame_graph.h"
}

namespace termin {

// Forward declarations
class CameraComponent;

// Viewport context for multi-viewport rendering
struct ViewportContext {
    std::string name;
    CameraComponent* camera = nullptr;
    Rect4i rect{0, 0, 0, 0};
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;
    FramebufferHandle* output_fbo = nullptr;
};

// C++ Render Engine
//
// Executes render pipelines using GraphicsBackend.
// Uses tc_frame_graph for dependency resolution and scheduling.
class RenderEngine {
public:
    GraphicsBackend* graphics = nullptr;

public:
    RenderEngine() = default;
    explicit RenderEngine(GraphicsBackend* graphics);

    // Render single view to target FBO
    // Parameters:
    //   pipeline: RenderPipeline containing passes, specs, and FBO pool
    //   target_fbo: target framebuffer (OUTPUT/DISPLAY)
    //   width, height: viewport size
    //   scene: scene to render
    //   camera: camera for view/projection
    //   lights: pre-built lights array
    //   layer_mask: layer mask for filtering entities
    void render_view_to_fbo(
        RenderPipeline* pipeline,
        FramebufferHandle* target_fbo,
        int width,
        int height,
        tc_scene* scene,
        CameraComponent* camera,
        tc_viewport* viewport,
        const std::vector<Light>& lights,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    // Render to screen (default framebuffer, null target_fbo)
    // Simplified interface for C# bindings
    void render_to_screen(
        RenderPipeline* pipeline,
        int width,
        int height,
        void* scene,  // tc_scene* as void* for SWIG
        CameraComponent* camera
    );

    // Present pipeline's color FBO to screen (blit to default framebuffer)
    // Call after render_to_screen to display the result
    void present_to_screen(
        RenderPipeline* pipeline,
        int width,
        int height,
        const std::string& resource_name = "color"
    );

    // Render pipeline with multiple viewports
    // Each pass selects viewport by viewport_name, writes to that viewport's output_fbo
    void render_scene_pipeline_offscreen(
        RenderPipeline* pipeline,
        tc_scene* scene,
        const std::unordered_map<std::string, ViewportContext>& viewport_contexts,
        const std::vector<Light>& lights,
        const std::string& default_viewport = ""
    );
};

} // namespace termin
