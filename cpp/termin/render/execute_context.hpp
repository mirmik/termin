#pragma once

#include <vector>
#include <unordered_map>
#include <string>
#include <cstdint>

#include "termin/render/frame_pass.hpp"
#include "termin/lighting/light.hpp"
#include "termin/tc_scene_ref.hpp"

extern "C" {
#include "tc_viewport.h"
}

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
 * - scene, camera, viewport: what to render
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
    tc_viewport* viewport = nullptr;
    std::vector<Light> lights;
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;
};

} // namespace termin
