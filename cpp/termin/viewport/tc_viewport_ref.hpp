#pragma once

// TcViewportRef - Non-owning reference to tc_viewport

extern "C" {
#include "render/tc_viewport.h"
}

namespace termin {

// Non-owning reference to a tc_viewport - for passing viewport context without ownership
class TcViewportRef {
public:
    tc_viewport* _v = nullptr;

    TcViewportRef() = default;
    explicit TcViewportRef(tc_viewport* v) : _v(v) {}

    bool is_valid() const { return _v != nullptr; }
    tc_viewport* ptr() const { return _v; }

    // Query properties (safe - returns defaults if nullptr)
    const char* name() const {
        return _v ? tc_viewport_get_name(_v) : "";
    }

    bool enabled() const {
        return _v ? tc_viewport_get_enabled(_v) : false;
    }

    int depth() const {
        return _v ? tc_viewport_get_depth(_v) : 0;
    }

    uint64_t layer_mask() const {
        return _v ? tc_viewport_get_layer_mask(_v) : 0xFFFFFFFFFFFFFFFFULL;
    }

    tc_scene_handle scene() const {
        return _v ? tc_viewport_get_scene(_v) : TC_SCENE_HANDLE_INVALID;
    }

    tc_component* camera() const {
        return _v ? tc_viewport_get_camera(_v) : nullptr;
    }

    tc_pipeline* pipeline() const {
        return _v ? tc_viewport_get_pipeline(_v) : nullptr;
    }

    bool has_internal_entities() const {
        return _v ? tc_viewport_has_internal_entities(_v) : false;
    }

    tc_entity_pool* internal_entities_pool() const {
        return _v ? tc_viewport_get_internal_entities_pool(_v) : nullptr;
    }

    tc_entity_id internal_entities_id() const {
        return _v ? tc_viewport_get_internal_entities_id(_v) : TC_ENTITY_ID_INVALID;
    }
};

} // namespace termin
