// tc_component_python_bindings.cpp - Python bindings for pure Python components
// This allows Python components to use tc_component directly without C++ Component wrapper.
#include <pybind11/pybind11.h>

#include "../../core_c/include/tc_component_python.h"
#include "../../core_c/include/tc_entity.h"
#include "entity/entity.hpp"

namespace py = pybind11;

namespace termin {

// ============================================================================
// Python callback implementations
// These are called from C code and dispatch to Python methods.
// GIL is NOT held when these are called (called from C update loop).
// ============================================================================

static void py_cb_start(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "start")) {
            self.attr("start")();
        }
    } catch (const py::error_already_set& e) {
        // Log but don't crash
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_update(void* py_self, float dt) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "update")) {
            self.attr("update")(dt);
        }
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_fixed_update(void* py_self, float dt) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "fixed_update")) {
            self.attr("fixed_update")(dt);
        }
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_destroy(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "on_destroy")) {
            self.attr("on_destroy")();
        }
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_added_to_entity(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        // Increment refcount to keep Python object alive while attached to entity.
        // Entity holds tc_component* which has data pointing to this Python object.
        // Without this, Python GC might collect the object while entity still uses it.
        Py_INCREF((PyObject*)py_self);

        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "on_added_to_entity")) {
            self.attr("on_added_to_entity")();
        }
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_removed_from_entity(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "on_removed_from_entity")) {
            self.attr("on_removed_from_entity")();
        }

        // Decrement refcount - entity no longer holds reference to this component.
        // This balances the Py_INCREF in on_added_to_entity.
        Py_DECREF((PyObject*)py_self);
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_added(void* py_self, void* scene) {
    // NOTE: scene here is tc_scene* from C, NOT PyObject*.
    // Python handles on_added() separately in Scene.add_non_recurse()
    // where it passes the correct Python Scene object.
    // So we do nothing here to avoid passing wrong pointer type.
    (void)py_self;
    (void)scene;
}

static void py_cb_on_removed(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "on_removed")) {
            self.attr("on_removed")();
        }
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_editor_start(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "on_editor_start")) {
            self.attr("on_editor_start")();
        }
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

// ============================================================================
// Initialization - called once to set up Python callbacks
// ============================================================================

static bool g_callbacks_initialized = false;

static void ensure_callbacks_initialized() {
    if (g_callbacks_initialized) return;

    tc_python_callbacks callbacks = {
        .start = py_cb_start,
        .update = py_cb_update,
        .fixed_update = py_cb_fixed_update,
        .on_destroy = py_cb_on_destroy,
        .on_added_to_entity = py_cb_on_added_to_entity,
        .on_removed_from_entity = py_cb_on_removed_from_entity,
        .on_added = py_cb_on_added,
        .on_removed = py_cb_on_removed,
        .on_editor_start = py_cb_on_editor_start,
    };

    tc_component_set_python_callbacks(&callbacks);
    g_callbacks_initialized = true;
}

// ============================================================================
// TcComponent wrapper for pure Python components
// ============================================================================

class TcComponent {
public:
    tc_component* _c = nullptr;
    std::string _interned_type_name;  // Keep type name alive

    // Create a new TcComponent wrapping a Python object
    // Note: py_self.ptr() is stored in _c->data (borrowed reference)
    // The Python object must outlive this TcComponent (which it does since
    // TcComponent is stored as _tc member of PythonComponent)
    TcComponent(py::object py_self, const std::string& type_name) {
        ensure_callbacks_initialized();

        // Intern type name
        _interned_type_name = type_name;

        // Create C component with Python vtable
        // Note: tc_component stores py_self.ptr() in _c->data (borrowed ref)
        _c = tc_component_new_python(py_self.ptr(), _interned_type_name.c_str());
    }

    ~TcComponent() {
        if (_c) {
            // Only free if not attached to an entity.
            // If attached, entity owns the component and will handle cleanup.
            if (_c->entity == nullptr) {
                tc_component_free_python(_c);
            }
            _c = nullptr;
        }
    }

    // Disable copy
    TcComponent(const TcComponent&) = delete;
    TcComponent& operator=(const TcComponent&) = delete;

    // Properties - delegate to tc_component fields
    bool get_enabled() const { return _c ? _c->enabled : true; }
    void set_enabled(bool v) { if (_c) _c->enabled = v; }

    bool get_active_in_editor() const { return _c ? _c->active_in_editor : false; }
    void set_active_in_editor(bool v) { if (_c) _c->active_in_editor = v; }

    bool get_is_native() const { return _c ? _c->is_native : false; }

    bool get_started() const { return _c ? _c->_started : false; }
    void set_started(bool v) { if (_c) _c->_started = v; }

    bool get_has_update() const { return _c ? _c->has_update : false; }
    void set_has_update(bool v) { if (_c) _c->has_update = v; }

    bool get_has_fixed_update() const { return _c ? _c->has_fixed_update : false; }
    void set_has_fixed_update(bool v) { if (_c) _c->has_fixed_update = v; }

    const char* type_name() const {
        return _c ? tc_component_type_name(_c) : "Component";
    }

    tc_component* c_ptr() { return _c; }

    // Return pointer as integer for interop
    uintptr_t c_ptr_int() const { return reinterpret_cast<uintptr_t>(_c); }

    // Get entity this component is attached to (or nullptr)
    tc_entity* get_entity() const {
        return _c ? _c->entity : nullptr;
    }
};

// ============================================================================
// Module bindings
// ============================================================================

void bind_tc_component_python(py::module_& m) {
    py::class_<TcComponent>(m, "TcComponent")
        .def(py::init<py::object, const std::string&>(),
             py::arg("py_self"), py::arg("type_name"))
        .def("type_name", &TcComponent::type_name)
        .def_property("enabled", &TcComponent::get_enabled, &TcComponent::set_enabled)
        .def_property("active_in_editor", &TcComponent::get_active_in_editor, &TcComponent::set_active_in_editor)
        .def_property_readonly("is_native", &TcComponent::get_is_native)
        .def_property("_started", &TcComponent::get_started, &TcComponent::set_started)
        .def_property("has_update", &TcComponent::get_has_update, &TcComponent::set_has_update)
        .def_property("has_fixed_update", &TcComponent::get_has_fixed_update, &TcComponent::set_has_fixed_update)
        .def("c_ptr_int", &TcComponent::c_ptr_int)
        .def_property_readonly("entity", [](TcComponent& self) -> Entity* {
            tc_entity* te = self.get_entity();
            return te ? entity_from_tc(te) : nullptr;
        }, py::return_value_policy::reference)
        ;
}

} // namespace termin
