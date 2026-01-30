#pragma once

// TcViewportRef - Non-owning reference to tc_viewport via handle

extern "C" {
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
}

namespace termin {

// Non-owning reference to a tc_viewport via handle - for passing viewport context
class TcViewportRef {
public:
    tc_viewport_handle handle_ = TC_VIEWPORT_HANDLE_INVALID;

    TcViewportRef() = default;
    explicit TcViewportRef(tc_viewport_handle h) : handle_(h) {}

    bool is_valid() const { return tc_viewport_alive(handle_); }
    tc_viewport_handle handle() const { return handle_; }

    // Query properties (safe - returns defaults if invalid)
    const char* name() const {
        return is_valid() ? tc_viewport_get_name(handle_) : "";
    }

    bool enabled() const {
        return is_valid() ? tc_viewport_get_enabled(handle_) : false;
    }

    int depth() const {
        return is_valid() ? tc_viewport_get_depth(handle_) : 0;
    }

    uint64_t layer_mask() const {
        return is_valid() ? tc_viewport_get_layer_mask(handle_) : 0xFFFFFFFFFFFFFFFFULL;
    }

    tc_scene_handle scene() const {
        return is_valid() ? tc_viewport_get_scene(handle_) : TC_SCENE_HANDLE_INVALID;
    }

    tc_component* camera() const {
        return is_valid() ? tc_viewport_get_camera(handle_) : nullptr;
    }

    tc_pipeline_handle pipeline() const {
        return is_valid() ? tc_viewport_get_pipeline(handle_) : TC_PIPELINE_HANDLE_INVALID;
    }

    bool has_internal_entities() const {
        return is_valid() ? tc_viewport_has_internal_entities(handle_) : false;
    }

    tc_entity_pool* internal_entities_pool() const {
        return is_valid() ? tc_viewport_get_internal_entities_pool(handle_) : nullptr;
    }

    tc_entity_id internal_entities_id() const {
        return is_valid() ? tc_viewport_get_internal_entities_id(handle_) : TC_ENTITY_ID_INVALID;
    }
};

} // namespace termin
