// tc_component_python_bindings.cpp - Drawable and input callback setup
// Core TcComponent binding lives in _scene_native.
// This file sets up termin-specific drawable and input dispatch callbacks.
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <unordered_map>

#include "tc_component_python.h"
#include <tgfx/resources/tc_material.h>
#include "core/tc_scene.h"
#include <tcbase/tc_log.hpp>
#include "render/drawable.hpp"
#include "render/render_context.hpp"
#include "tc_component_python_bindings.hpp"
#include "input/input_events.hpp"

namespace nb = nanobind;

namespace termin {

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
static std::unordered_map<void*, std::vector<GeometryDrawCall>> g_py_geometry_draw_cache;

static void* py_drawable_cb_get_geometry_draws(void* py_self, const char* phase_mark) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    void* result = nullptr;
    try {
        nb::handle self((PyObject*)py_self);
        if (nb::hasattr(self, "get_geometry_draws")) {
            std::string pm = phase_mark ? phase_mark : "";
            nb::object py_draws = self.attr("get_geometry_draws")(pm.empty() ? nb::none() : nb::cast(pm));

            auto& cached = g_py_geometry_draw_cache[py_self];
            cached.clear();

            if (!py_draws.is_none()) {
                for (auto item : py_draws) {
                    GeometryDrawCall dc;
                    nb::object phase_obj = item.attr("phase");
                    if (!phase_obj.is_none()) {
                        try {
                            dc.phase = nb::cast<tc_material_phase*>(phase_obj);
                        } catch (const nb::cast_error&) {
                            continue;
                        }
                    }
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

static void py_input_cb_on_mouse_button(void* py_self, tc_mouse_button_event* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        termin::MouseButtonEvent cpp_event(*event);
        nb::object py_event = nb::cast(cpp_event);
        self.attr("on_mouse_button")(py_event);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_mouse_button");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_input_cb_on_mouse_move(void* py_self, tc_mouse_move_event* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        termin::MouseMoveEvent cpp_event(*event);
        nb::object py_event = nb::cast(cpp_event);
        self.attr("on_mouse_move")(py_event);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_mouse_move");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_input_cb_on_scroll(void* py_self, tc_scroll_event* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        termin::ScrollEvent cpp_event(*event);
        nb::object py_event = nb::cast(cpp_event);
        self.attr("on_scroll")(py_event);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_scroll");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

static void py_input_cb_on_key(void* py_self, tc_key_event* event) {
    PyGILState_STATE gstate = PyGILState_Ensure();
    try {
        nb::handle self((PyObject*)py_self);
        termin::KeyEvent cpp_event(*event);
        nb::object py_event = nb::cast(cpp_event);
        self.attr("on_key")(py_event);
    } catch (const std::exception& e) {
        tc::Log::error(e, "InputHandler::on_key");
        PyErr_Print();
    }
    PyGILState_Release(gstate);
}

// ============================================================================
// Init function — sets up drawable and input callbacks (called once)
// ============================================================================

static bool g_callbacks_initialized = false;

void init_python_component_callbacks() {
    if (g_callbacks_initialized) return;

    // Drawable callbacks (termin-specific: RenderContext, GeometryDrawCall)
    tc_python_drawable_callbacks drawable_callbacks = {
        .has_phase = py_drawable_cb_has_phase,
        .draw_geometry = py_drawable_cb_draw_geometry,
        .get_geometry_draws = py_drawable_cb_get_geometry_draws,
    };
    tc_component_set_python_drawable_callbacks(&drawable_callbacks);

    // Input handler callbacks (termin-specific: MouseButtonEvent etc.)
    tc_python_input_callbacks input_callbacks = {
        .on_mouse_button = py_input_cb_on_mouse_button,
        .on_mouse_move = py_input_cb_on_mouse_move,
        .on_scroll = py_input_cb_on_scroll,
        .on_key = py_input_cb_on_key,
    };
    tc_component_set_python_input_callbacks(&input_callbacks);

    g_callbacks_initialized = true;
}

} // namespace termin
