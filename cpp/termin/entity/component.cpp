// component.cpp - CxxComponent implementation
#include "component.hpp"
#include "tc_log.hpp"

namespace termin {

// Static vtable for C++ components - dispatches to virtual methods
const tc_component_vtable CxxComponent::_cxx_vtable = {
    // Lifecycle
    CxxComponent::_cb_start,
    CxxComponent::_cb_update,
    CxxComponent::_cb_fixed_update,
    CxxComponent::_cb_before_render,
    CxxComponent::_cb_on_destroy,
    // Entity relationship
    CxxComponent::_cb_on_added_to_entity,
    CxxComponent::_cb_on_removed_from_entity,
    // Scene relationship
    CxxComponent::_cb_on_added,
    CxxComponent::_cb_on_removed,
    CxxComponent::_cb_on_scene_inactive,
    CxxComponent::_cb_on_scene_active,
    // Editor
    CxxComponent::_cb_on_editor_start,
    CxxComponent::_cb_setup_editor_defaults,
    // Memory management
    CxxComponent::_cb_drop,
    // Reference counting - for Python wrapper
    CxxComponent::_cb_retain,
    CxxComponent::_cb_release,
    // Serialization - NULL, handled by InspectRegistry
    nullptr,
    nullptr
};

CxxComponent::CxxComponent() {
    // Initialize the C component structure
    tc_component_init(&_c, &_cxx_vtable);
    _c.kind = TC_CXX_COMPONENT;
    // Note: type_entry is set by the registry when component is created via factory
    // Set default flags
    _c.enabled = true;
    _c.active_in_editor = false;
    _c._started = false;
    _c.has_update = false;
    _c.has_fixed_update = false;
    _c.has_before_render = false;
}

CxxComponent::~CxxComponent() {
}

void CxxComponent::release() {
    int prev = _ref_count.fetch_sub(1);
    if (prev <= 1) {
        delete this;
    }
}

void CxxComponent::link_type_entry(const char* type_name) {
    tc_type_entry* entry = tc_component_registry_get_entry(type_name);
    if (entry) {
        _c.type_entry = entry;
        _c.type_version = entry->version;
    }
}

// Static callbacks that dispatch to C++ virtual methods
void CxxComponent::_cb_start(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->start();
        c->_started = true;
    }
}

void CxxComponent::_cb_update(tc_component* c, float dt) {
    auto* self = from_tc(c);
    if (self) {
        self->update(dt);
    }
}

void CxxComponent::_cb_fixed_update(tc_component* c, float dt) {
    auto* self = from_tc(c);
    if (self) {
        self->fixed_update(dt);
    }
}

void CxxComponent::_cb_before_render(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->before_render();
    }
}

void CxxComponent::_cb_on_destroy(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->on_destroy();
    }
}

void CxxComponent::_cb_on_added_to_entity(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        // entity() now reads from c->owner_pool/owner_entity_id directly
        self->on_added_to_entity();
    }
}

void CxxComponent::_cb_on_removed_from_entity(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->on_removed_from_entity();
        // entity() will return invalid after c->owner_pool is cleared
    }
}

void CxxComponent::_cb_on_added(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->on_added();
    }
}

void CxxComponent::_cb_on_removed(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->on_removed();
    }
}

void CxxComponent::_cb_on_scene_inactive(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->on_scene_inactive();
    }
}

void CxxComponent::_cb_on_scene_active(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->on_scene_active();
    }
}

void CxxComponent::_cb_on_editor_start(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->on_editor_start();
    }
}

void CxxComponent::_cb_setup_editor_defaults(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->setup_editor_defaults();
    }
}

// Memory management callbacks
void CxxComponent::_cb_drop(tc_component* c) {
    auto* self = from_tc(c);
    // Don't delete if externally managed - external language owns the object
    if (self && !c->externally_managed) {
        delete self;
    }
}

void CxxComponent::_cb_retain(tc_component* c) {
    if (!c) return;
    // If externally managed, incref the body (C#/Rust wrapper)
    if (c->externally_managed && c->body) {
        tc_component_body_incref(c->body);
    } else {
        auto* self = from_tc(c);
        if (self) {
            self->retain();
        }
    }
}

void CxxComponent::_cb_release(tc_component* c) {
    if (!c) return;
    // If externally managed, decref the body (C#/Rust wrapper)
    if (c->externally_managed && c->body) {
        tc_component_body_decref(c->body);
    } else {
        auto* self = from_tc(c);
        if (self) {
            self->release();  // May delete self if ref_count reaches 0
        }
    }
}

} // namespace termin
