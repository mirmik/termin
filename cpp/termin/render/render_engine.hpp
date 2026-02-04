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
#include "termin/tc_scene.hpp"

extern "C" {
#include "render/tc_frame_graph.h"
#include "render/tc_viewport_pool.h"
#include "core/tc_scene.h"
}

namespace termin {

// Forward declarations
class CameraComponent;

// Build lights from scene's LightComponents
// Iterates all LightComponent in scene and calls to_light()
std::vector<Light> build_lights_from_scene(tc_scene_handle scene);

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

    // Render single view to target FBO (builds lights from scene automatically)
    void render_view_to_fbo(
        RenderPipeline* pipeline,
        FramebufferHandle* target_fbo,
        int width,
        int height,
        tc_scene_handle scene,
        CameraComponent* camera,
        tc_viewport_handle viewport,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    // Render single view to target FBO (with explicit lights array)
    void render_view_to_fbo(
        RenderPipeline* pipeline,
        FramebufferHandle* target_fbo,
        int width,
        int height,
        tc_scene_handle scene,
        CameraComponent* camera,
        tc_viewport_handle viewport,
        const std::vector<Light>& lights,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    // Render to screen (default framebuffer, null target_fbo)
    void render_to_screen(
        RenderPipeline* pipeline,
        int width,
        int height,
        tc_scene_handle scene,
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

    // Render pipeline with multiple viewports (builds lights from scene automatically)
    void render_scene_pipeline_offscreen(
        RenderPipeline* pipeline,
        tc_scene_handle scene,
        const std::unordered_map<std::string, ViewportContext>& viewport_contexts,
        const std::string& default_viewport = ""
    );

    // Render pipeline with multiple viewports (with explicit lights array)
    void render_scene_pipeline_offscreen(
        RenderPipeline* pipeline,
        tc_scene_handle scene,
        const std::unordered_map<std::string, ViewportContext>& viewport_contexts,
        const std::vector<Light>& lights,
        const std::string& default_viewport = ""
    );
};

} // namespace termin
