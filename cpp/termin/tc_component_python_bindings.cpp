// tc_component_python_bindings.cpp - Python bindings for pure Python components
// This allows Python components to use tc_component directly without C++ Component wrapper.
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <unordered_map>

#include "tc_component_python.h"
#include "../../core_c/include/tc_material.h"
#include "../../core_c/include/tc_scene.h"
#include "tc_log.hpp"
#include "render/drawable.hpp"
#include "render/render_context.hpp"
#include "tc_component_python_bindings.hpp"
#include "entity/entity.hpp"

namespace nb = nanobind;

namespace termin {

// ============================================================================
// Python callback implementations
// These are called from C code and dispatch to Python methods.
// GIL is NOT held when these are called (called from C update loop).
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
// Drawable callback implementations
// ============================================================================

static bool py_drawable_cb_has_phase(void* py_self, const char* phase_mark) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    bool result = false;
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "phase_marks")) {
            nb::object marks = self.attr("phase_marks");
            if (!marks.is_none()) {
                std::string pm = phase_mark ? phase_mark : "";
                result = nb::cast<bool>(marks.attr("__contains__")(pm));
            }
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "Drawable::has_phase");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
    return result;
}

static void py_drawable_cb_draw_geometry(void* py_self, void* render_context, int geometry_id) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "draw_geometry")) {
            // Cast C++ RenderContext pointer to Python object
            RenderContext* ctx = static_cast<RenderContext*>(render_context);
            nb::object py_ctx = nb::cast(ctx, nb::rv_policy::reference);

            self.attr("draw_geometry")(py_ctx, geometry_id);
        }
    } catch (const std::exception& e) {
        tc::Log::warn(e, "Drawable::draw_geometry");
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
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "get_geometry_draws")) {
            std::string pm = phase_mark ? phase_mark : "";
            nb::object py_draws = self.attr("get_geometry_draws")(pm.empty() ? nb::none() : nb::cast(pm));

            // Convert Python list to C++ vector
            auto& cached = g_py_geometry_draw_cache[py_self];
            cached.clear();

            if (!py_draws.is_none()) {
                for (auto item : py_draws) {
                    GeometryDrawCall dc;
                    // Get phase from draw call
                    nb::object phase_obj = item.attr("phase");
                    if (!phase_obj.is_none()) {
                        // Try to cast to tc_material_phase* (new C-based material system)
                        try {
                            dc.phase = nb::cast<tc_material_phase*>(phase_obj);
                        } catch (const nb::cast_error&) {
                            // Phase is old MaterialPhase* type - skip this draw call
                            // Python components using old material system will not render
                            // until they are migrated to tc_material
                            continue;
                        }
                    }
                    // Get geometry_id
                    nb::object gid_obj = item.attr("geometry_id");
                    if (!gid_obj.is_none()) {
                        dc.geometry_id = nb::cast<int>(gid_obj);
                    }
                    cached.push_back(dc);
                }
            }
            result = &cached;
        }
    } catch (const std::exception& e) {
        tc::Log::error(e, "Drawable::get_geometry_draws");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
    return result;
}

// ============================================================================
// Input handler callback implementations
// ============================================================================

static void py_input_cb_on_mouse_button(void* py_self, void* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        nb::handle event_obj((PyObject*)event);
        self.attr("on_mouse_button")(event_obj);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_mouse_button");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_input_cb_on_mouse_move(void* py_self, void* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        nb::handle event_obj((PyObject*)event);
        self.attr("on_mouse_move")(event_obj);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_mouse_move");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_input_cb_on_scroll(void* py_self, void* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        nb::handle event_obj((PyObject*)event);
        self.attr("on_scroll")(event_obj);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_scroll");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_input_cb_on_key(void* py_self, void* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        nb::handle event_obj((PyObject*)event);
        self.attr("on_key")(event_obj);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_key");
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
        PyObject* obj = (PyObject*)py_obj;
        Py_ssize_t refcnt = Py_REFCNT(obj);
        PyObject* type = PyObject_Type(obj);
        const char* type_name = type ? ((PyTypeObject*)type)->tp_name : "unknown";
        tc::Log::debug("[py_cb_decref] type=%s refcnt_before=%zd obj=%p", type_name, refcnt, py_obj);
        Py_XDECREF(type);
        Py_DECREF(obj);
        tc::Log::debug("[py_cb_decref] done");
        PyGILState_Release(gstate);
    }
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
        .on_scene_inactive = py_cb_on_scene_inactive,
        .on_scene_active = py_cb_on_scene_active,
        .on_editor_start = py_cb_on_editor_start,
        .incref = py_cb_incref,
        .decref = py_cb_decref,
    };
    tc_component_set_python_callbacks(&callbacks);

    // Set up drawable callbacks
    tc_python_drawable_callbacks drawable_callbacks = {
        .has_phase = py_drawable_cb_has_phase,
        .draw_geometry = py_drawable_cb_draw_geometry,
        .get_geometry_draws = py_drawable_cb_get_geometry_draws,
    };
    tc_component_set_python_drawable_callbacks(&drawable_callbacks);

    // Set up input handler callbacks
    tc_python_input_callbacks input_callbacks = {
        .on_mouse_button = py_input_cb_on_mouse_button,
        .on_mouse_move = py_input_cb_on_mouse_move,
        .on_scroll = py_input_cb_on_scroll,
        .on_key = py_input_cb_on_key,
    };
    tc_component_set_python_input_callbacks(&input_callbacks);

    g_callbacks_initialized = true;
}

// ============================================================================
// TcComponent wrapper for pure Python components
// ============================================================================

class TcComponent {
public:
    tc_component* _c = nullptr;

    // Create a new TcComponent wrapping a Python object
    // The TcComponent owns the tc_component, which lives as long as PythonComponent.
    // NO retain here - Entity will do retain when component is added.
    TcComponent(nb::object py_self, const std::string& type_name) {
        ensure_callbacks_initialized();

        // Create C component with Python vtable (owns type_name copy)
        // body points to py_self, native_language = TC_BINDING_PYTHON
        _c = tc_component_new_python(py_self.ptr(), type_name.c_str());
    }

    ~TcComponent() {
        if (_c) {
            // Just free the tc_component struct, don't touch Python refcount
            // Entity already released if it was added
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

    // Install input vtable (call when Python component implements InputHandler)
    void install_input_vtable() {
        if (_c) {
            tc_component_install_python_input_vtable(_c);
        }
    }

    // Check if input vtable is installed
    bool is_input_handler() const {
        return _c && _c->input_vtable != nullptr;
    }

    // Get owner entity (returns invalid Entity if not attached)
    Entity entity() const {
        if (_c && _c->owner_pool) {
            return Entity(_c->owner_pool, _c->owner_entity_id);
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
        .def_prop_ro("entity", &TcComponent::entity)
        ;
}

} // namespace termin
