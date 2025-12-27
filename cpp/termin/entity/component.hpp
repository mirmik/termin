#pragma once

#include <string>
#include <cstdint>
#include <unordered_set>
#include <pybind11/pybind11.h>
#include "../../trent/trent.h"
#include "../inspect/inspect_registry.hpp"
#include "../../../core_c/include/tc_component.h"

namespace py = pybind11;

namespace termin {

class Entity;  // Forward declaration

// Base class for all components.
// Both C++ and Python components inherit from this.
// C++ components use REGISTER_COMPONENT macro for auto-registration.
// Python components register via Component.__init_subclass__.
//
// Internally wraps tc_component (C core) for future Scene integration.
class ENTITY_API Component {
public:
    virtual ~Component();

    // Type identification (for serialization)
    const char* type_name() const { return _type_name; }

    // Set type name with string interning to avoid dangling pointers
    void set_type_name(const char* name) {
        static std::unordered_set<std::string> interned_names;
        auto [it, _] = interned_names.insert(name);
        _type_name = it->c_str();
        // Sync to C component
        _c.type_name = _type_name;
    }

    // Lifecycle hooks (virtual - subclasses override these)
    virtual void start() {}
    virtual void update(float dt) { (void)dt; }
    virtual void fixed_update(float dt) { (void)dt; }
    virtual void on_destroy() {}
    virtual void on_editor_start() {}

    // Editor hooks
    virtual void setup_editor_defaults() {}  // Called when created via editor UI

    // Called when added/removed from entity
    virtual void on_added_to_entity() {}
    virtual void on_removed_from_entity() {}

    // Called when entity is added/removed from scene
    virtual void on_added(py::object scene) { (void)scene; }
    virtual void on_removed() {}

    // Serialization - uses InspectRegistry for INSPECT_FIELD properties.
    // DO NOT OVERRIDE in derived components!
    virtual nos::trent serialize_data() const {
        return InspectRegistry::instance().serialize_all(
            const_cast<void*>(static_cast<const void*>(this)),
            _type_name
        );
    }
    virtual void deserialize_data(const nos::trent& data) {
        InspectRegistry::instance().deserialize_all(
            static_cast<void*>(this),
            _type_name,
            data
        );
    }

    nos::trent serialize() const {
        nos::trent result;
        result["type"] = _type_name;
        result["data"] = serialize_data();
        return result;
    }

    // Flags (public fields for backward compatibility)
    // These are synced to the internal tc_component structure
    bool enabled = true;
    bool active_in_editor = false;
    bool is_native = false;
    bool _started = false;
    bool has_update = false;
    bool has_fixed_update = false;

    // Owner entity (set by Entity::add_component)
    Entity* entity = nullptr;

    // Access to underlying C component (for Scene integration)
    // Note: Call sync_to_c() before using the C component
    tc_component* c_component() { return &_c; }
    const tc_component* c_component() const { return &_c; }

    // Sync C++ fields to C structure (call before C code uses _c)
    void sync_to_c() {
        _c.enabled = enabled;
        _c.active_in_editor = active_in_editor;
        _c.is_native = is_native;
        _c._started = _started;
        _c.has_update = has_update;
        _c.has_fixed_update = has_fixed_update;
        _c.type_name = _type_name;
    }

    // Sync C structure back to C++ fields (call after C code modifies _c)
    void sync_from_c() {
        enabled = _c.enabled;
        active_in_editor = _c.active_in_editor;
        is_native = _c.is_native;
        _started = _c._started;
        has_update = _c.has_update;
        has_fixed_update = _c.has_fixed_update;
    }

protected:
    Component();
    const char* _type_name = "Component";

    // Internal C component structure
    tc_component _c;

private:
    // Static vtable for C++ components - dispatches to virtual methods
    static const tc_component_vtable _cpp_vtable;

    // Static callbacks that dispatch to C++ virtual methods
    static void _cb_start(tc_component* c);
    static void _cb_update(tc_component* c, float dt);
    static void _cb_fixed_update(tc_component* c, float dt);
    static void _cb_on_destroy(tc_component* c);
    static void _cb_on_added_to_entity(tc_component* c);
    static void _cb_on_removed_from_entity(tc_component* c);
    static void _cb_on_added(tc_component* c, void* scene);
    static void _cb_on_removed(tc_component* c);
    static void _cb_on_editor_start(tc_component* c);
    static void _cb_setup_editor_defaults(tc_component* c);
};

} // namespace termin
