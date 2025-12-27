// component.cpp - Component implementation with tc_component wrapper
#include "component.hpp"

namespace termin {

// Static vtable for C++ components - dispatches to virtual methods
const tc_component_vtable Component::_cpp_vtable = {
    // type_name - set per-instance via _c.type_name, not here
    "Component",
    // Lifecycle
    Component::_cb_start,
    Component::_cb_update,
    Component::_cb_fixed_update,
    Component::_cb_on_destroy,
    // Entity relationship
    Component::_cb_on_added_to_entity,
    Component::_cb_on_removed_from_entity,
    // Scene relationship
    Component::_cb_on_added,
    Component::_cb_on_removed,
    // Editor
    Component::_cb_on_editor_start,
    Component::_cb_setup_editor_defaults,
    // Memory management - NULL since Component is managed by C++/Python
    nullptr,
    // Serialization - NULL, handled by InspectRegistry
    nullptr,
    nullptr
};

Component::Component() {
    // Initialize the C component structure
    tc_component_init(&_c, &_cpp_vtable);
    _c.data = this;  // Store 'this' for callbacks
    _c.type_name = _type_name;
    // Sync initial flags
    _c.enabled = enabled;
    _c.active_in_editor = active_in_editor;
    _c.is_native = is_native;
    _c._started = _started;
    _c.has_update = has_update;
    _c.has_fixed_update = has_fixed_update;
}

Component::~Component() {
    // Nothing special needed - _c is embedded, not dynamically allocated
}

// Static callbacks that dispatch to C++ virtual methods
void Component::_cb_start(tc_component* c) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        self->start();
        self->_started = true;
        c->_started = true;
    }
}

void Component::_cb_update(tc_component* c, float dt) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        self->update(dt);
    }
}

void Component::_cb_fixed_update(tc_component* c, float dt) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        self->fixed_update(dt);
    }
}

void Component::_cb_on_destroy(tc_component* c) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        self->on_destroy();
    }
}

void Component::_cb_on_added_to_entity(tc_component* c) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        self->on_added_to_entity();
    }
}

void Component::_cb_on_removed_from_entity(tc_component* c) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        self->on_removed_from_entity();
    }
}

void Component::_cb_on_added(tc_component* c, void* scene) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        // Convert void* back to py::object
        // Note: scene is actually passed as nullptr here since we don't have the py::object
        // The actual on_added is called from Python/C++ with proper py::object
        (void)scene;
        // self->on_added(py::reinterpret_borrow<py::object>(scene));
    }
}

void Component::_cb_on_removed(tc_component* c) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        self->on_removed();
    }
}

void Component::_cb_on_editor_start(tc_component* c) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        self->on_editor_start();
    }
}

void Component::_cb_setup_editor_defaults(tc_component* c) {
    auto* self = static_cast<Component*>(c->data);
    if (self) {
        self->setup_editor_defaults();
    }
}

} // namespace termin
