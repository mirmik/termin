// tc_scene_ref.hpp - Non-owning reference to tc_scene
#pragma once

#include "../../core_c/include/tc_scene.h"

namespace termin {

// Non-owning reference to a tc_scene - for passing scene context without ownership
class TcSceneRef {
public:
    tc_scene* _s = nullptr;

    TcSceneRef() = default;
    explicit TcSceneRef(tc_scene* s) : _s(s) {}

    bool valid() const { return _s != nullptr; }
    tc_scene* ptr() const { return _s; }
};

} // namespace termin
