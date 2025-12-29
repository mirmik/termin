// tc_component_python_bindings.cpp - Python bindings for pure Python components
// This allows Python components to use tc_component directly without C++ Component wrapper.
#include <pybind11/pybind11.h>
#include <unordered_map>
#include <cstdio>

#include "../../core_c/include/tc_component_python.h"
#include "../../core_c/include/tc_log.h"
#include "render/drawable.hpp"
#include "render/render_context.hpp"

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
        if (py::hasattr(self, "on_added")) {
            // Get Python Scene from get_current_scene()
            py::object scene_module = py::module_::import("termin.visualization.core.scene._scene");
            py::object py_scene = scene_module.attr("get_current_scene")();
            self.attr("on_added")(py_scene);
        }
    } catch (const py::error_already_set& e) {
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
// Drawable callback implementations
// ============================================================================

static bool py_drawable_cb_has_phase(void* py_self, const char* phase_mark) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    bool result = false;
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "phase_marks")) {
            py::object marks = self.attr("phase_marks");
            if (!marks.is_none()) {
                std::string pm = phase_mark ? phase_mark : "";
                result = marks.attr("__contains__")(pm).cast<bool>();
            }
        }
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
    return result;
}

static void py_drawable_cb_draw_geometry(void* py_self, void* render_context, const char* geometry_id) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "draw_geometry")) {
            // Cast C++ RenderContext pointer to Python object
            RenderContext* ctx = static_cast<RenderContext*>(render_context);
            py::object py_ctx = py::cast(ctx, py::return_value_policy::reference);

            std::string gid = geometry_id ? geometry_id : "";
            self.attr("draw_geometry")(py_ctx, gid);
        }
    } catch (const py::error_already_set& e) {
        tc_log_warn("[Drawable] Python draw_geometry exception: %s", e.what());
    }
    PyGILState_Release(gstate);
}

// Cached geometry draws for Python drawables
// Each Python drawable gets its own cached vector (keyed by py_self pointer)
static std::unordered_map<void*, std::vector<GeometryDrawCall>> g_py_geometry_draw_cache;

static void* py_drawable_cb_get_geometry_draws(void* py_self, const char* phase_mark) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    void* result = nullptr;
    try {
        py::handle self((PyObject*)py_self);
        if (py::hasattr(self, "get_geometry_draws")) {
            std::string pm = phase_mark ? phase_mark : "";
            py::object py_draws = self.attr("get_geometry_draws")(pm.empty() ? py::none() : py::cast(pm));

            // Convert Python list to C++ vector
            auto& cached = g_py_geometry_draw_cache[py_self];
            cached.clear();

            if (!py_draws.is_none()) {
                for (auto item : py_draws) {
                    GeometryDrawCall dc;
                    // Get phase from draw call
                    py::object phase_obj = item.attr("phase");
                    if (!phase_obj.is_none()) {
                        dc.phase = phase_obj.cast<MaterialPhase*>();
                    }
                    // Get geometry_id
                    py::object gid_obj = item.attr("geometry_id");
                    if (!gid_obj.is_none()) {
                        dc.geometry_id = gid_obj.cast<std::string>();
                    }
                    cached.push_back(dc);
                }
            }
            result = &cached;
        }
    } catch (const py::error_already_set& e) {
        PyErr_Print();
    }
    PyGILState_Release(gstate);
    return result;
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

    // Set up drawable callbacks
    tc_python_drawable_callbacks drawable_callbacks = {
        .has_phase = py_drawable_cb_has_phase,
        .draw_geometry = py_drawable_cb_draw_geometry,
        .get_geometry_draws = py_drawable_cb_get_geometry_draws,
    };
    tc_component_set_python_drawable_callbacks(&drawable_callbacks);

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

    // Install drawable vtable (call when Python component implements Drawable)
    void install_drawable_vtable() {
        if (_c) {
            tc_component_install_python_drawable_vtable(_c);
        }
    }

    // Check if drawable vtable is installed
    bool is_drawable() const {
        return _c && _c->drawable_vtable != nullptr;
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
        .def_property_readonly("is_cxx_component", &TcComponent::is_cxx_component)
        .def_property_readonly("is_python_component", &TcComponent::is_python_component)
        .def_property("_started", &TcComponent::get_started, &TcComponent::set_started)
        .def_property("has_update", &TcComponent::get_has_update, &TcComponent::set_has_update)
        .def_property("has_fixed_update", &TcComponent::get_has_fixed_update, &TcComponent::set_has_fixed_update)
        .def("c_ptr_int", &TcComponent::c_ptr_int)
        .def("install_drawable_vtable", &TcComponent::install_drawable_vtable)
        .def_property_readonly("is_drawable", &TcComponent::is_drawable)
        ;
}

} // namespace termin
