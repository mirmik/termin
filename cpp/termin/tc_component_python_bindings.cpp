// tc_component_python_bindings.cpp - Python bindings for pure Python components
// This allows Python components to use tc_component directly without C++ Component wrapper.
#include <pybind11/pybind11.h>

#include "../../core_c/include/tc_component_python.h"

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
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_added(void* py_self, void* scene) {
    (void)scene;  // tc_scene* - not used, we use get_current_scene() instead
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        py::handle self((PyObject*)py_self);
        py::object type_name = py::str(py::type::of(self).attr("__name__"));
        printf("[py_cb_on_added] Component type: %s\n", type_name.cast<std::string>().c_str());
        fflush(stdout);

        if (py::hasattr(self, "on_added")) {
            // Get Python Scene from get_current_scene()
            py::object scene_module = py::module_::import("termin.visualization.core.scene._scene");
            py::object py_scene = scene_module.attr("get_current_scene")();
            printf("[py_cb_on_added] Calling on_added, scene=%p\n", py_scene.ptr());
            fflush(stdout);
            self.attr("on_added")(py_scene);
            printf("[py_cb_on_added] on_added returned\n");
            fflush(stdout);
        } else {
            printf("[py_cb_on_added] No on_added method\n");
            fflush(stdout);
        }
    } catch (const py::error_already_set& e) {
        printf("[py_cb_on_added] Exception!\n");
        fflush(stdout);
        PyErr_Print();
    }
    PyGILState_Release(gstate);
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
    py::object _py_self;  // Strong reference to Python object
    std::string _interned_type_name;  // Keep type name alive

    // Create a new TcComponent wrapping a Python object
    TcComponent(py::object py_self, const std::string& type_name) {
        ensure_callbacks_initialized();

        // Keep Python object alive
        _py_self = py_self;

        // Intern type name
        _interned_type_name = type_name;

        // Create C component with Python vtable
        _c = tc_component_new_python(py_self.ptr(), _interned_type_name.c_str());
    }

    ~TcComponent() {
        if (_c) {
            tc_component_free_python(_c);
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

    bool is_cxx_component() const { return _c ? _c->kind == TC_CXX_COMPONENT : false; }
    bool is_python_component() const { return _c ? _c->kind == TC_PYTHON_COMPONENT : true; }

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
        .def_property_readonly("is_cxx_component", &TcComponent::is_cxx_component)
        .def_property_readonly("is_python_component", &TcComponent::is_python_component)
        .def_property("_started", &TcComponent::get_started, &TcComponent::set_started)
        .def_property("has_update", &TcComponent::get_has_update, &TcComponent::set_has_update)
        .def_property("has_fixed_update", &TcComponent::get_has_fixed_update, &TcComponent::set_has_fixed_update)
        .def("c_ptr_int", &TcComponent::c_ptr_int)
        ;
}

} // namespace termin
