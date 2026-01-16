#pragma once

#include <string>
#include <cstdint>
#include <cstddef>
#include <unordered_set>
#include <nanobind/nanobind.h>
#include "../../trent/trent.h"
#include "../inspect/inspect_registry.hpp"
#include "../../../core_c/include/tc_component.h"
#include "../../../core_c/include/tc_inspect.hpp"
#include "../../../core_c/include/tc_entity_pool.h"
#include "entity.hpp"

namespace nb = nanobind;

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

    // Owner entity (set by Entity::add_component)
    Entity entity;

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
    const char* type_name() const { return _c.type_name; }

    // Set type name with string interning to avoid dangling pointers
    void set_type_name(const char* name) {
        static std::unordered_set<std::string> interned_names;
        auto [it, _] = interned_names.insert(name);
        _c.type_name = it->c_str();
    }

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

    // Called when entity is added/removed from scene
    virtual void on_added(nb::object scene) { (void)scene; }
    virtual void on_removed() {}
    virtual void on_scene_inactive() {}
    virtual void on_scene_active() {}

    // Serialization - uses C API tc_inspect for INSPECT_FIELD properties.
    virtual nos::trent serialize_data() const {
        tc_value v = tc_inspect_serialize(
            const_cast<void*>(static_cast<const void*>(this)),
            type_name()
        );
        nos::trent result = tc::tc_value_to_trent(&v);
        tc_value_free(&v);
        return result;
    }

    virtual void deserialize_data(const nos::trent& data, tc_scene* scene = nullptr) {
        tc_value v = tc::trent_to_tc_value(data);
        tc_inspect_deserialize_with_scene(
            static_cast<void*>(this),
            type_name(),
            &v,
            scene
        );
        tc_value_free(&v);
    }

    nos::trent serialize() const {
        nos::trent result;
        result["type"] = type_name();
        result["data"] = serialize_data();
        return result;
    }

    // Access to underlying C component (for Scene integration)
    tc_component* c_component() { return &_c; }
    const tc_component* c_component() const { return &_c; }

    // Get Python wrapper for this component (cached in _c.py_wrap)
    nb::object to_python() {
        if (!_c.py_wrap) {
            nb::object wrapper = nb::cast(this, nb::rv_policy::reference);
            _c.py_wrap = wrapper.inc_ref().ptr();
        }
        return nb::borrow<nb::object>(
            reinterpret_cast<PyObject*>(_c.py_wrap)
        );
    }

    // Set cached Python wrapper (called from bindings when component is created)
    void set_py_wrap(nb::object self) {
        if (_c.py_wrap) {
            nb::handle old(reinterpret_cast<PyObject*>(_c.py_wrap));
            old.dec_ref();
        }
        _c.py_wrap = self.inc_ref().ptr();
    }

    // Convert any tc_component to Python object
    static nb::object tc_to_python(tc_component* c) {
        if (!c) return nb::none();

        if (c->kind == TC_CXX_COMPONENT) {
            CxxComponent* cxx = from_tc(c);
            if (!cxx) return nb::none();
            return cxx->to_python();
        } else {
            // TC_PYTHON_COMPONENT: py_wrap holds the Python object
            if (!c->py_wrap) return nb::none();
            return nb::borrow<nb::object>(
                reinterpret_cast<PyObject*>(c->py_wrap)
            );
        }
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
    static void _cb_on_added(tc_component* c, void* scene);
    static void _cb_on_removed(tc_component* c);
    static void _cb_on_scene_inactive(tc_component* c);
    static void _cb_on_scene_active(tc_component* c);
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
