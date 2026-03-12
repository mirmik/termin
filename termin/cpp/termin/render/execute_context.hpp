#pragma once

#include <vector>
#include <unordered_map>
#include <string>
#include <cstdint>

#include "termin/render/frame_pass.hpp"
#include <termin/render/light.hpp>
#include <termin/tc_scene.hpp>
#include "termin/tc_scene_render_ext.hpp"
#include <core/tc_entity_pool.h>

namespace termin {

// Forward declarations
class CameraComponent;

/**
 * Context passed to CxxFramePass.execute().
 *
 * Contains all data needed by passes to render:
 * - graphics: graphics backend
 * - reads_fbos/writes_fbos: FBO maps for input/output
 * - rect: pixel rectangle for rendering
 * - scene, camera: what to render
 * - viewport_name/internal_entities: auxiliary render-target context
 * - lights: pre-computed lights
 * - layer_mask: which entity layers to render
 */
struct ExecuteContext {
    GraphicsBackend* graphics = nullptr;
    FBOMap reads_fbos;
    FBOMap writes_fbos;
    Rect4i rect;
    TcSceneRef scene;
    CameraComponent* camera = nullptr;
    std::string viewport_name;
    tc_entity_handle internal_entities = TC_ENTITY_HANDLE_INVALID;
    std::vector<Light> lights;
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;
};

} // namespace termin
