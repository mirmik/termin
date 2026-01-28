#pragma once

#include <string>
#include <cstdint>
#include <cstddef>
#include <atomic>
#include <unordered_set>
#include "../../../core_c/include/tc_component.h"
#include "../../../core_c/include/tc_inspect_cpp.hpp"
#include "../../../core_c/include/tc_entity_pool.h"
#include "../tc_scene_ref.hpp"
#include "entity.hpp"

namespace termin {

// Base class for all C++ components.
// C++ components use REGISTER_COMPONENT macro for auto-registration.
//
// tc_component is embedded as first member, allowing container_of to work.
// Lifetime is managed via reference counting (_ref_count).
// Components start with ref_count=0 and are retained when added to entity.
class ENTITY_API CxxComponent {
public:
    // --- Fields (public) ---

    // Embedded C component (MUST be first member for from_tc to work)
    tc_component _c;

    // Owner entity - constructed from C-side owner_pool/owner_entity_id
    Entity entity() const {
        return Entity(_c.owner_pool, _c.owner_entity_id);
    }

private:
    // --- Fields (private) ---

    // Reference count for lifetime management
    // Starts at 0, incremented by entity on add, decremented on remove
    // When reaches 0 after being >0, component deletes itself
    std::atomic<int> _ref_count{0};

    // Static vtable for C++ components - dispatches to virtual methods
    static const tc_component_vtable _cxx_vtable;

public:
    // --- Methods ---

    virtual ~CxxComponent();

    // Get CxxComponent* from tc_component* (uses offsetof since _c is first member)
    // Returns nullptr if c is not a CxxComponent (e.g., Python component)
    static CxxComponent* from_tc(tc_component* c) {
        if (!c || c->kind != TC_CXX_COMPONENT) return nullptr;
        return reinterpret_cast<CxxComponent*>(
            reinterpret_cast<char*>(c) - offsetof(CxxComponent, _c)
        );
    }

    // Reference counting for lifetime management
    void retain() { ++_ref_count; }
    void release();  // Defined in .cpp - may delete this
    int ref_count() const { return _ref_count.load(); }

    // Get tc_component pointer (for C API interop)
    tc_component* tc_component_ptr() { return &_c; }
    const tc_component* tc_component_ptr() const { return &_c; }

    // Alias for compatibility
    tc_component* c_component() { return &_c; }
    const tc_component* c_component() const { return &_c; }

    // Setup external wrapper (for C#/Rust/other bindings)
    // Caller is responsible for preventing wrapper from being GC'd
    void set_external_body(void* body) {
        tc_component_set_external_body(&_c, body);
    }

    // Check if externally managed
    bool externally_managed() const { return _c.externally_managed; }

    // Type identification (for serialization) - uses type_entry from registry
    const char* type_name() const {
        return tc_component_type_name(&_c);
    }

protected:
    // Link component to type registry entry by name.
    // Call from derived class constructor: link_type_entry("MeshRenderer");
    // This enables proper type identification for scene iteration.
    void link_type_entry(const char* type_name);

public:
    // Accessors for tc_component flags
    bool enabled() const { return _c.enabled; }
    void set_enabled(bool v) { _c.enabled = v; }

    bool active_in_editor() const { return _c.active_in_editor; }
    void set_active_in_editor(bool v) { _c.active_in_editor = v; }

    bool started() const { return _c._started; }
    void set_started(bool v) { _c._started = v; }

    bool has_update() const { return _c.has_update; }
    void set_has_update(bool v) { _c.has_update = v; }

    bool has_fixed_update() const { return _c.has_fixed_update; }
    void set_has_fixed_update(bool v) { _c.has_fixed_update = v; }

    bool has_before_render() const { return _c.has_before_render; }
    void set_has_before_render(bool v) { _c.has_before_render = v; }

    // Check if component handles input events (has input_vtable installed)
    bool is_input_handler() const { return tc_component_is_input_handler(&_c); }

    // Lifecycle hooks (virtual - subclasses override these)
    virtual void start() {}
    virtual void update(float dt) { (void)dt; }
    virtual void fixed_update(float dt) { (void)dt; }
    virtual void before_render() {}
    virtual void on_destroy() {}
    virtual void on_editor_start() {}

    // Editor hooks
    virtual void setup_editor_defaults() {}  // Called when created via editor UI

    // Called when added/removed from entity
    virtual void on_added_to_entity() {}
    virtual void on_removed_from_entity() {}

    // Called after component is fully attached to entity
    virtual void on_added() {}
    virtual void on_removed() {}
    virtual void on_scene_inactive() {}
    virtual void on_scene_active() {}

    // Serialization - uses C API tc_inspect for INSPECT_FIELD properties.
    // Returns tc_value that caller must free with tc_value_free()
    virtual tc_value serialize_data() const {
        return tc_inspect_serialize(
            const_cast<void*>(static_cast<const void*>(this)),
            type_name()
        );
    }

    virtual void deserialize_data(const tc_value* data, tc_scene* scene = nullptr) {
        if (!data) return;
        tc_inspect_deserialize(
            static_cast<void*>(this),
            type_name(),
            data,
            scene
        );
    }

    // Full serialize (type + data) - returns tc_value dict
    tc_value serialize() const {
        tc_value result = tc_value_dict_new();
        tc_value_dict_set(&result, "type", tc_value_string(type_name()));
        tc_value data = serialize_data();
        tc_value_dict_set(&result, "data", data);
        // Note: dict_set takes ownership, don't free data
        return result;
    }

protected:
    CxxComponent();

private:
    // Static callbacks that dispatch to C++ virtual methods
    static void _cb_start(tc_component* c);
    static void _cb_update(tc_component* c, float dt);
    static void _cb_fixed_update(tc_component* c, float dt);
    static void _cb_before_render(tc_component* c);
    static void _cb_on_destroy(tc_component* c);
    static void _cb_on_added_to_entity(tc_component* c);
    static void _cb_on_removed_from_entity(tc_component* c);
    static void _cb_on_added(tc_component* c);
    static void _cb_on_removed(tc_component* c);
    static void _cb_on_scene_inactive(tc_component* c);
    static void _cb_on_scene_active(tc_component* c);
    static void _cb_on_editor_start(tc_component* c);
    static void _cb_setup_editor_defaults(tc_component* c);

    // Memory management callbacks
    static void _cb_drop(tc_component* c);
    static void _cb_retain(tc_component* c);
    static void _cb_release(tc_component* c);
};

// Alias for backward compatibility during migration
using Component = CxxComponent;

// Template definition for Entity::get_component<T>()
// Defined here after CxxComponent is fully declared
template<typename T>
T* Entity::get_component() {
    size_t count = component_count();
    for (size_t i = 0; i < count; i++) {
        tc_component* tc = component_at(i);
        if (tc && tc->kind == TC_CXX_COMPONENT) {
            CxxComponent* comp = CxxComponent::from_tc(tc);
            T* typed = dynamic_cast<T*>(comp);
            if (typed) return typed;
        }
    }
    return nullptr;
}

} // namespace termin
