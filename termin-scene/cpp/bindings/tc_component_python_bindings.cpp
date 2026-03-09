// tc_component_python_bindings.cpp - Core TcComponent binding for _scene_native
// Drawable and input callback setup stays in termin/_native.
#include <termin/bindings/tc_component_python_bindings.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <tcbase/tc_log.hpp>
#include <termin/entity/entity.hpp>

extern "C" {
#include "tc_component_python.h"
}

namespace nb = nanobind;

namespace termin {

// ============================================================================
// Core Python callback implementations
// Called from C code, dispatch to Python methods.
// GIL is NOT held when called (from C update loop).
// ============================================================================

static void py_cb_start(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "start")) {
            self.attr("start")();
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::start");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_update(void* py_self, float dt) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "update")) {
            self.attr("update")(dt);
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::update");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_fixed_update(void* py_self, float dt) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "fixed_update")) {
            self.attr("fixed_update")(dt);
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::fixed_update");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_destroy(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "on_destroy")) {
            self.attr("on_destroy")();
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::on_destroy");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_added_to_entity(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "on_added_to_entity")) {
            self.attr("on_added_to_entity")();
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::on_added_to_entity");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_removed_from_entity(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "on_removed_from_entity")) {
            self.attr("on_removed_from_entity")();
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::on_removed_from_entity");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_added(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "on_added")) {
            self.attr("on_added")();
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::on_added");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_removed(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "on_removed")) {
            self.attr("on_removed")();
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::on_removed");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_scene_inactive(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "on_scene_inactive")) {
            self.attr("on_scene_inactive")();
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::on_scene_inactive");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_scene_active(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "on_scene_active")) {
            self.attr("on_scene_active")();
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::on_scene_active");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_cb_on_editor_start(void* py_self) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "on_editor_start")) {
            self.attr("on_editor_start")();
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "PythonComponent::on_editor_start");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

// ============================================================================
// Reference counting callbacks
// ============================================================================

static void py_cb_incref(void* py_obj) {
    if (py_obj) {
        PyGILState_STATE gstate = PyGILState_Ensure();
        Py_INCREF((PyObject*)py_obj);
        PyGILState_Release(gstate);
    }
}

static void py_cb_decref(void* py_obj) {
    if (py_obj) {
        PyGILState_STATE gstate = PyGILState_Ensure();
        Py_DECREF((PyObject*)py_obj);
        PyGILState_Release(gstate);
    }
}

// ============================================================================
// Initialization - called once to set up core Python callbacks
// ============================================================================

static bool g_core_callbacks_initialized = false;

static void ensure_core_callbacks_initialized() {
    if (g_core_callbacks_initialized) return;

    tc_python_callbacks callbacks = {
        .start = py_cb_start,
        .update = py_cb_update,
        .fixed_update = py_cb_fixed_update,
        .on_destroy = py_cb_on_destroy,
        .on_added_to_entity = py_cb_on_added_to_entity,
        .on_removed_from_entity = py_cb_on_removed_from_entity,
        .on_added = py_cb_on_added,
        .on_removed = py_cb_on_removed,
        .on_scene_inactive = py_cb_on_scene_inactive,
        .on_scene_active = py_cb_on_scene_active,
        .on_editor_start = py_cb_on_editor_start,
        .incref = py_cb_incref,
        .decref = py_cb_decref,
    };
    tc_component_set_python_callbacks(&callbacks);

    g_core_callbacks_initialized = true;
}

// ============================================================================
// TcComponent wrapper for pure Python components
// ============================================================================

class TcComponent {
public:
    tc_component* _c = nullptr;

    // Create a new TcComponent wrapping a Python object.
    // NO retain here - Entity will do retain when component is added.
    TcComponent(nb::object py_self, const std::string& type_name) {
        ensure_core_callbacks_initialized();
        _c = tc_component_new_python(py_self.ptr(), type_name.c_str());
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

    // Properties
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
    uintptr_t c_ptr_int() const { return reinterpret_cast<uintptr_t>(_c); }

    // Install drawable vtable
    void install_drawable_vtable() {
        if (_c) {
            tc_component_install_python_drawable_vtable(_c);
        }
    }

    bool is_drawable() const {
        return _c && _c->drawable_vtable != nullptr;
    }

    // Install input vtable
    void install_input_vtable() {
        if (_c) {
            tc_component_install_python_input_vtable(_c);
        }
    }

    bool is_input_handler() const {
        return _c && _c->input_vtable != nullptr;
    }

    // Get owner entity
    Entity entity() const {
        if (_c && tc_entity_handle_valid(_c->owner)) {
            return Entity(_c->owner);
        }
        return Entity();
    }
};

// ============================================================================
// Module bindings
// ============================================================================

void bind_tc_component_python(nb::module_& m) {
    nb::class_<TcComponent>(m, "TcComponent")
        .def(nb::init<nb::object, const std::string&>(),
             nb::arg("py_self"), nb::arg("type_name"))
        .def("type_name", &TcComponent::type_name)
        .def_prop_rw("enabled", &TcComponent::get_enabled, &TcComponent::set_enabled)
        .def_prop_rw("active_in_editor", &TcComponent::get_active_in_editor, &TcComponent::set_active_in_editor)
        .def_prop_ro("is_cxx_component", &TcComponent::is_cxx_component)
        .def_prop_ro("is_python_component", &TcComponent::is_python_component)
        .def_prop_rw("_started", &TcComponent::get_started, &TcComponent::set_started)
        .def_prop_rw("has_update", &TcComponent::get_has_update, &TcComponent::set_has_update)
        .def_prop_rw("has_fixed_update", &TcComponent::get_has_fixed_update, &TcComponent::set_has_fixed_update)
        .def("c_ptr_int", &TcComponent::c_ptr_int)
        .def("install_drawable_vtable", &TcComponent::install_drawable_vtable)
        .def_prop_ro("is_drawable", &TcComponent::is_drawable)
        .def("install_input_vtable", &TcComponent::install_input_vtable)
        .def_prop_ro("is_input_handler", &TcComponent::is_input_handler)
        .def_prop_ro("entity", &TcComponent::entity);
}

} // namespace termin
