// component.cpp - CxxComponent implementation
#include <termin/entity/component.hpp>
#include <tcbase/tc_log.hpp>
#include <utility>

namespace termin {

void register_component_base_inspect_fields() {
    static bool registered = false;
    if (registered) {
        return;
    }

    tc::InspectFieldInfo display_name_field;
    display_name_field.type_name = "Component";
    display_name_field.path = "display_name";
    display_name_field.label = "Name";
    display_name_field.kind = "string";
    display_name_field.is_serializable = false;
    display_name_field.is_inspectable = true;
    display_name_field.getter = [](void* obj) -> tc_value {
        return tc_value_string(static_cast<CxxComponent*>(obj)->display_name().c_str());
    };
    display_name_field.setter = [](void* obj, tc_value value, void*) {
        if (value.type == TC_VALUE_STRING) {
            static_cast<CxxComponent*>(obj)->set_display_name(value.data.s ? value.data.s : "");
        }
    };
    tc::InspectRegistry::instance().add_field_with_choices("Component", std::move(display_name_field));

    tc::InspectRegistry::instance().add_with_accessors<CxxComponent, bool>(
        "Component", "enabled", "Enabled", "bool",
        [](CxxComponent* c) { return c->enabled(); },
        [](CxxComponent* c, bool v) { c->set_enabled(v); }
    );

    registered = true;
}

// C++ ref_vtable: retain/release use internal _ref_count, drop deletes
static void cxx_ref_retain(tc_component* c) {
    auto* self = CxxComponent::from_tc(c);
    if (self) self->retain();
}

static void cxx_ref_release(tc_component* c) {
    auto* self = CxxComponent::from_tc(c);
    if (self) self->release();
}

static void cxx_ref_drop(tc_component* c) {
    auto* self = CxxComponent::from_tc(c);
    if (self) delete self;
}

const tc_component_ref_vtable g_cxx_component_ref_vtable = {
    cxx_ref_retain,
    cxx_ref_release,
    cxx_ref_drop,
};

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
    // Render lifecycle
    CxxComponent::_cb_on_render_attach,
    CxxComponent::_cb_on_render_detach,
    // Editor
    CxxComponent::_cb_on_editor_start,
    CxxComponent::_cb_setup_editor_defaults,
    // Serialization - NULL, handled by InspectRegistry
    nullptr,
    nullptr
};

CxxComponent::CxxComponent(const char* type_name) {
    tc_component_init(&_c, &_cxx_vtable);
    _c.ref_vtable = &g_cxx_component_ref_vtable;
    _c.kind = TC_CXX_COMPONENT;
    _c.body = this;
    _c.native_language = TC_LANGUAGE_CXX;
    _c.enabled = true;
    _c.active_in_editor = false;
    _c._started = false;
    _c.has_update = false;
    _c.has_fixed_update = false;
    _c.has_before_render = false;
    tc_component_set_declared_type_name(&_c, type_name);
    tc_type_entry* entry = tc_component_registry_get_entry(type_name);
    if (entry) {
        _c.type_entry = entry;
        _c.type_version = entry->version;
    }
}

CxxComponent::~CxxComponent() {
    tc_component_unlink_from_registry(&_c);
}

void CxxComponent::release() {
    int prev = _ref_count.fetch_sub(1);
    if (prev <= 1) {
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
    if (self) self->update(dt);
}

void CxxComponent::_cb_fixed_update(tc_component* c, float dt) {
    auto* self = from_tc(c);
    if (self) self->fixed_update(dt);
}

void CxxComponent::_cb_before_render(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->before_render();
}

void CxxComponent::_cb_on_destroy(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_destroy();
}

void CxxComponent::_cb_on_added_to_entity(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_added_to_entity();
}

void CxxComponent::_cb_on_removed_from_entity(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_removed_from_entity();
}

void CxxComponent::_cb_on_added(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_added();
}

void CxxComponent::_cb_on_removed(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_removed();
}

void CxxComponent::_cb_on_scene_inactive(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_scene_inactive();
}

void CxxComponent::_cb_on_scene_active(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_scene_active();
}

void CxxComponent::_cb_on_render_attach(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_render_attach();
}

void CxxComponent::_cb_on_render_detach(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_render_detach();
}

void CxxComponent::_cb_on_editor_start(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->on_editor_start();
}

void CxxComponent::_cb_setup_editor_defaults(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->setup_editor_defaults();
}

} // namespace termin
