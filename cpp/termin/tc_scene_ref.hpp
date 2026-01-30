// tc_scene_ref.hpp - Non-owning reference to tc_scene via handle
#pragma once

#include "../../core_c/include/tc_scene.h"
#include "../../core_c/include/tc_scene_pool.h"

namespace termin {

// Non-owning reference to a tc_scene via handle
// Safe to store - handle validation prevents use-after-free
class TcSceneRef {
public:
    tc_scene_handle _h = TC_SCENE_HANDLE_INVALID;

    TcSceneRef() = default;
    explicit TcSceneRef(tc_scene_handle h) : _h(h) {}

    bool valid() const { return tc_scene_alive(_h); }
    tc_scene_handle handle() const { return _h; }

    // Convenience accessors that delegate to tc_scene_* functions
    tc_entity_pool* entity_pool() const { return tc_scene_entity_pool(_h); }
    tc_scene_lighting* lighting() const { return tc_scene_get_lighting(_h); }
    tc_scene_skybox* skybox() const { return tc_scene_get_skybox(_h); }
};

} // namespace termin
