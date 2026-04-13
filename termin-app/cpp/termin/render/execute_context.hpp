#pragma once

#include <vector>
#include <unordered_map>
#include <string>
#include <cstdint>

#include "termin/render/frame_pass.hpp"
#include <termin/render/render_camera.hpp>
#include <termin/render/light.hpp>
#include <termin/tc_scene.hpp>
#include "termin/tc_scene_render_ext.hpp"
#include <core/tc_entity_pool.h>

// Forward declaration — tgfx2 is the new backend-neutral graphics API.
// Passes that have been migrated to Phase 2 use ctx2 instead of graphics.
// Legacy passes continue to use graphics; both pointers are valid
// simultaneously during the dual-path migration window.
namespace tgfx2 {
class RenderContext2;
}

namespace termin {

/**
 * Context passed to CxxFramePass.execute().
 *
 * Contains all data needed by passes to render:
 * - graphics: legacy tgfx graphics backend (state-machine API).
 * - ctx2: tgfx2 mid-level render context (pipeline+command-buffer API).
 *   Non-null during the Phase 2 dual-path window. Passes that have been
 *   migrated should prefer ctx2; unmigrated passes keep using graphics.
 * - reads_fbos/writes_fbos: FBO maps for input/output
 * - rect: pixel rectangle for rendering
 * - scene, camera: what to render
 * - viewport_name/internal_entities: auxiliary render-target context
 * - lights: pre-computed lights
 * - layer_mask: which entity layers to render
 */
struct ExecuteContext {
    GraphicsBackend* graphics = nullptr;
    tgfx2::RenderContext2* ctx2 = nullptr;
    FBOMap reads_fbos;
    FBOMap writes_fbos;
    Rect4i rect;
    TcSceneRef scene;
    RenderCamera* camera = nullptr;
    std::string viewport_name;
    tc_entity_handle internal_entities = TC_ENTITY_HANDLE_INVALID;
    std::vector<Light> lights;
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;
};

} // namespace termin
