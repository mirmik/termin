#pragma once

#include <string>
#include <cstdint>
#include <cstddef>
#include <unordered_set>
#include <pybind11/pybind11.h>
#include "../../trent/trent.h"
#include "../inspect/inspect_registry.hpp"
#include "../../../core_c/include/tc_component.h"
#include "../../../core_c/include/tc_entity_pool.h"
#include "entity.hpp"

namespace py = pybind11;

namespace termin {

// Base class for all C++ components.
// C++ components use REGISTER_COMPONENT macro for auto-registration.
//
// tc_component is embedded as first member, allowing container_of to work.
class ENTITY_API CxxComponent {
public:
    // --- Fields (public) ---

    // Embedded C component (MUST be first member for from_tc to work)
    tc_component _c;

    // Flags (synced to internal tc_component structure)
    bool enabled = true;
    bool active_in_editor = false;
    bool _started = false;
    bool has_update = false;
    bool has_fixed_update = false;

    // Owner entity (set by Entity::add_component)
    Entity entity;

protected:
    // --- Fields (protected) ---

    const char* _type_name = "CxxComponent";

private:
    // --- Fields (private) ---

    // Static vtable for C++ components - dispatches to virtual methods
    static const tc_component_vtable _cxx_vtable;

public:
    // --- Methods ---

    virtual ~CxxComponent();

    // Get CxxComponent* from tc_component* (uses offsetof since _c is first member)
    static CxxComponent* from_tc(tc_component* c) {
        if (!c) return nullptr;
        return reinterpret_cast<CxxComponent*>(
            reinterpret_cast<char*>(c) - offsetof(CxxComponent, _c)
        );
    }

    // Type identification (for serialization)
    const char* type_name() const { return _type_name; }

    // Set type name with string interning to avoid dangling pointers
    void set_type_name(const char* name) {
        static std::unordered_set<std::string> interned_names;
        auto [it, _] = interned_names.insert(name);
        _type_name = it->c_str();
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

    // Access to underlying C component (for Scene integration)
    tc_component* c_component() { return &_c; }
    const tc_component* c_component() const { return &_c; }

    // Get Python wrapper for this component (cached in _c.py_wrap)
    py::object to_python() {
        if (!_c.py_wrap) {
            py::object wrapper = py::cast(this, py::return_value_policy::reference);
            _c.py_wrap = wrapper.inc_ref().ptr();
        }
        return py::reinterpret_borrow<py::object>(
            reinterpret_cast<PyObject*>(_c.py_wrap)
        );
    }

    // Set cached Python wrapper (called from bindings when component is created)
    void set_py_wrap(py::object self) {
        if (_c.py_wrap) {
            py::handle old(reinterpret_cast<PyObject*>(_c.py_wrap));
            old.dec_ref();
        }
        _c.py_wrap = self.inc_ref().ptr();
    }

    // Convert any tc_component to Python object
    static py::object tc_to_python(tc_component* c) {
        if (!c) return py::none();
        if (c->kind == TC_CXX_COMPONENT) {
            CxxComponent* cxx = from_tc(c);
            return cxx ? cxx->to_python() : py::none();
        } else {
            // TC_PYTHON_COMPONENT: py_wrap holds the Python object
            if (!c->py_wrap) return py::none();
            return py::reinterpret_borrow<py::object>(
                reinterpret_cast<PyObject*>(c->py_wrap)
            );
        }
    }

    // Sync C++ fields to C structure (call before C code uses _c)
    void sync_to_c() {
        _c.enabled = enabled;
        _c.active_in_editor = active_in_editor;
        _c._started = _started;
        _c.has_update = has_update;
        _c.has_fixed_update = has_fixed_update;
        _c.type_name = _type_name;
    }

    // Sync C structure back to C++ fields (call after C code modifies _c)
    void sync_from_c() {
        enabled = _c.enabled;
        active_in_editor = _c.active_in_editor;
        _started = _c._started;
        has_update = _c.has_update;
        has_fixed_update = _c.has_fixed_update;
    }

protected:
    CxxComponent();

private:
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
