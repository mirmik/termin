// component.cpp - CxxComponent implementation
#include "component.hpp"
#include "tc_log.hpp"

#ifdef TERMIN_HAS_NANOBIND
#include <nanobind/nanobind.h>
namespace nb = nanobind;
#endif

namespace termin {

// Static vtable for C++ components - dispatches to virtual methods
const tc_component_vtable CxxComponent::_cxx_vtable = {
    // type_name - set per-instance via _c.type_name, not here
    "CxxComponent",
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
    set_type_name("CxxComponent");
    // Set default flags
    _c.enabled = true;
    _c.active_in_editor = false;
    _c._started = false;
    _c.has_update = false;
    _c.has_fixed_update = false;
    _c.has_before_render = false;
}

CxxComponent::~CxxComponent() {
#ifdef TERMIN_HAS_NANOBIND
    // Release Python binding if we have one
    void* py_binding = tc_component_get_binding(&_c, TC_BINDING_PYTHON);
    if (py_binding && Py_IsInitialized()) {
        nb::gil_scoped_acquire gil;
        nb::handle py_wrapper(reinterpret_cast<PyObject*>(py_binding));
        py_wrapper.dec_ref();
        tc_component_clear_binding(&_c, TC_BINDING_PYTHON);
    }
#endif
}

void CxxComponent::release() {
    int prev = _ref_count.fetch_sub(1);
    tc::Log::debug("[CxxComponent::release] type=%s prev_ref=%d", type_name(), prev);
    if (prev <= 1) {
        // ref_count reached 0 - delete self
        tc::Log::debug("[CxxComponent::release] deleting %s", type_name());
        delete this;
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
        self->on_added_to_entity();
    }
}

void CxxComponent::_cb_on_removed_from_entity(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->on_removed_from_entity();
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
    if (self) {
        delete self;
    }
}

void CxxComponent::_cb_retain(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->retain();
    }
}

void CxxComponent::_cb_release(tc_component* c) {
    auto* self = from_tc(c);
    if (self) {
        self->release();  // May delete self if ref_count reaches 0
    }
}

} // namespace termin
