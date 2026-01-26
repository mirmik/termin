#pragma once

#include <string>
#include <unordered_map>
#include <memory>
#include <vector>

#include "termin/render/graphics_backend.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/lighting/light.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/tc_scene_ref.hpp"

extern "C" {
#include "tc_frame_graph.h"
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

// FBO Pool entry (move-only because of unique_ptr)
struct FBOPoolEntry {
    std::string key;
    FramebufferHandlePtr fbo;
    int width = 0;
    int height = 0;
    int samples = 1;
    std::string format;
    bool external = false;

    FBOPoolEntry() = default;
    FBOPoolEntry(FBOPoolEntry&&) = default;
    FBOPoolEntry& operator=(FBOPoolEntry&&) = default;
    FBOPoolEntry(const FBOPoolEntry&) = delete;
    FBOPoolEntry& operator=(const FBOPoolEntry&) = delete;
};

// FBO Pool - manages framebuffer allocation and reuse
class FBOPool {
public:
    std::vector<FBOPoolEntry> entries;

    FramebufferHandle* ensure(
        GraphicsBackend* graphics,
        const std::string& key,
        int width,
        int height,
        int samples = 1,
        const std::string& format = ""
    );

    FramebufferHandle* get(const std::string& key);
    void set(const std::string& key, FramebufferHandle* fbo);
    void clear();
};

// C++ Render Engine
//
// Executes render pipelines using GraphicsBackend.
// Uses tc_frame_graph for dependency resolution and scheduling.
class RenderEngine {
public:
    GraphicsBackend* graphics = nullptr;

private:
    FBOPool fbo_pool_;
    std::unordered_map<std::string, std::unique_ptr<ShadowMapArrayResource>> shadow_arrays_;

public:
    RenderEngine() = default;
    explicit RenderEngine(GraphicsBackend* graphics);

    // Non-copyable (FBOPool contains unique_ptr)
    RenderEngine(const RenderEngine&) = delete;
    RenderEngine& operator=(const RenderEngine&) = delete;

    // Movable
    RenderEngine(RenderEngine&&) = default;
    RenderEngine& operator=(RenderEngine&&) = default;

    // Render single view to target FBO
    // Parameters:
    //   pipeline: RenderPipeline containing passes and specs
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

    // Render pipeline with multiple viewports
    // Each pass selects viewport by viewport_name, writes to that viewport's output_fbo
    void render_scene_pipeline_offscreen(
        RenderPipeline* pipeline,
        tc_scene* scene,
        const std::unordered_map<std::string, ViewportContext>& viewport_contexts,
        const std::vector<Light>& lights,
        const std::string& default_viewport = ""
    );

    // Clear FBO pool
    void clear_fbo_pool() { fbo_pool_.clear(); }

    // Access FBO pool for external management
    FBOPool& fbo_pool() { return fbo_pool_; }
};

} // namespace termin
