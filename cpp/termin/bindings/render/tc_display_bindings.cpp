// tc_display_bindings.cpp - Python bindings for TcDisplay
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/vector.h>

#include "termin/render/tc_display_handle.hpp"
#include "termin/viewport/tc_viewport_handle.hpp"

extern "C" {
#include "render/tc_render_surface.h"
#include "tc_scene.h"
#include "tc_component.h"
}

namespace nb = nanobind;

namespace termin {

// Helper to convert viewport handle
static std::tuple<uint32_t, uint32_t> vh_to_tuple(tc_viewport_handle h) {
    return {h.index, h.generation};
}

static tc_viewport_handle tuple_to_vh(const std::tuple<uint32_t, uint32_t>& t) {
    tc_viewport_handle h;
    h.index = std::get<0>(t);
    h.generation = std::get<1>(t);
    return h;
}

void bind_tc_display(nb::module_& m) {
    // TcDisplay class binding
    nb::class_<TcDisplay>(m, "Display",
        "Display - render target with viewports.\n\n"
        "Wraps tc_display from core_c. Contains surface and viewport list.")

        // Constructor with surface pointer
        .def("__init__", [](TcDisplay* self, uintptr_t surface_ptr, const std::string& name,
                            bool editor_only, const std::string& uuid) {
            tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(surface_ptr);
            new (self) TcDisplay(surface, name);
            if (!uuid.empty()) {
                self->set_uuid(uuid);
            }
            self->set_editor_only(editor_only);
        }, nb::arg("surface_ptr"), nb::arg("name") = "Display",
           nb::arg("editor_only") = false, nb::arg("uuid") = "")

        .def("is_valid", &TcDisplay::is_valid)

        .def_prop_ro("tc_display_ptr", [](TcDisplay& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.ptr());
        }, "Raw pointer to tc_display (for C interop)")

        // Properties
        .def_prop_rw("name",
            &TcDisplay::name,
            &TcDisplay::set_name,
            "Display name")

        .def_prop_rw("uuid",
            &TcDisplay::uuid,
            &TcDisplay::set_uuid,
            "Unique identifier (for serialization)")

        .def_prop_ro("runtime_id", [](TcDisplay& self) -> uint64_t {
            std::string u = self.uuid();
            return std::hash<std::string>{}(u);
        }, "64-bit hash of UUID (for fast runtime lookup)")

        .def_prop_rw("editor_only",
            &TcDisplay::editor_only,
            &TcDisplay::set_editor_only,
            "If True, display is created and rendered only in editor")

        .def_prop_rw("enabled",
            &TcDisplay::enabled,
            &TcDisplay::set_enabled,
            "If True, display is rendered. If False, display is skipped")

        .def_prop_ro("surface_ptr", [](TcDisplay& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.surface());
        }, "Raw pointer to tc_render_surface")

        // Size
        .def("get_size", [](TcDisplay& self) {
            return self.get_size();
        }, "Return display size in pixels as (width, height)")

        // Viewport management - returns TcViewport objects
        .def_prop_ro("viewports", [](TcDisplay& self) -> std::vector<TcViewport> {
            std::vector<TcViewport> result;
            size_t count = self.viewport_count();
            for (size_t i = 0; i < count; ++i) {
                tc_viewport_handle vh = self.viewport_at_index(i);
                if (tc_viewport_handle_valid(vh)) {
                    result.push_back(TcViewport(vh));
                }
            }
            return result;
        }, "List of viewports")

        .def("add_viewport", [](TcDisplay& self, TcViewport& vp) {
            self.add_viewport(vp.handle());
            // Update pixel rect
            auto [w, h] = self.get_size();
            vp.update_pixel_rect(w, h);
        }, nb::arg("viewport"), "Add viewport to display")

        .def("remove_viewport", [](TcDisplay& self, TcViewport& vp) {
            self.remove_viewport(vp.handle());
        }, nb::arg("viewport"), "Remove viewport from display")

        // Viewport lookup
        .def("viewport_at", [](TcDisplay& self, float x, float y) -> nb::object {
            // Transform y: screen coordinates (top-down) -> OpenGL (bottom-up)
            float ny = 1.0f - y;
            tc_viewport_handle vh = self.viewport_at(x, ny);
            if (!tc_viewport_handle_valid(vh)) {
                return nb::none();
            }
            return nb::cast(TcViewport(vh));
        }, nb::arg("x"), nb::arg("y"),
           "Find viewport at normalized coordinates [0..1], origin top-left")

        .def("viewport_at_pixels", [](TcDisplay& self, float px, float py) -> nb::object {
            tc_viewport_handle vh = self.viewport_at_screen(px, py);
            if (!tc_viewport_handle_valid(vh)) {
                return nb::none();
            }
            return nb::cast(TcViewport(vh));
        }, nb::arg("px"), nb::arg("py"),
           "Find viewport at pixel coordinates, origin top-left")

        .def("update_all_pixel_rects", &TcDisplay::update_all_pixel_rects,
             "Recalculate pixel_rect for all viewports. Call on surface resize.")

        // Context operations
        .def("make_current", &TcDisplay::make_current,
             "Make render context current")

        .def("present", &TcDisplay::swap_buffers,
             "Present rendered result (swap buffers)")

        // Create viewport helper
        .def("create_viewport", [](TcDisplay& self,
                                   nb::object scene_obj,
                                   nb::object camera_obj,
                                   std::tuple<float, float, float, float> rect,
                                   const std::string& name) -> TcViewport {
            // Get scene handle
            tc_scene_handle scene_h = TC_SCENE_HANDLE_INVALID;
            if (!scene_obj.is_none()) {
                auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene_obj.attr("scene_handle")());
                scene_h.index = std::get<0>(h);
                scene_h.generation = std::get<1>(h);
            }

            // Get camera component pointer
            tc_component* camera_ptr = nullptr;
            if (!camera_obj.is_none()) {
                camera_ptr = reinterpret_cast<tc_component*>(
                    nb::cast<uintptr_t>(camera_obj.attr("c_component_ptr")())
                );
            }

            // Create viewport
            TcViewport vp = TcViewport::create(name, scene_h, camera_ptr);
            vp.set_rect(std::get<0>(rect), std::get<1>(rect),
                       std::get<2>(rect), std::get<3>(rect));

            // Add to display
            self.add_viewport(vp.handle());

            // Update pixel rect
            auto [w, h] = self.get_size();
            vp.update_pixel_rect(w, h);

            // Add viewport to camera's list
            if (!camera_obj.is_none()) {
                camera_obj.attr("add_viewport")(vp);
            }

            return vp;
        }, nb::arg("scene").none(), nb::arg("camera").none(),
           nb::arg("rect") = std::make_tuple(0.0f, 0.0f, 1.0f, 1.0f),
           nb::arg("name") = "main",
           "Create and add new viewport (set pipeline separately via viewport.pipeline)")

        // Static factory
        .def_static("_from_ptr", [](uintptr_t ptr, bool owned) {
            return TcDisplay::from_ptr(reinterpret_cast<tc_display*>(ptr), owned);
        }, nb::arg("ptr"), nb::arg("owned") = false,
           "Create TcDisplay from raw pointer")
    ;

    // Keep old _display_* functions for backwards compatibility during migration
    m.def("_display_new", [](uintptr_t surface_ptr, const std::string& name) -> uintptr_t {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(surface_ptr);
        tc_display* d = tc_display_new(name.c_str(), surface);
        return reinterpret_cast<uintptr_t>(d);
    }, nb::arg("surface_ptr"), nb::arg("name"));

    m.def("_display_free", [](uintptr_t ptr) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) tc_display_free(d);
    }, nb::arg("ptr"));

    m.def("_display_get_name", [](uintptr_t ptr) -> std::string {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return "";
        const char* name = tc_display_get_name(d);
        return name ? name : "";
    }, nb::arg("ptr"));

    m.def("_display_set_name", [](uintptr_t ptr, const std::string& name) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) tc_display_set_name(d, name.c_str());
    }, nb::arg("ptr"), nb::arg("name"));

    m.def("_display_get_uuid", [](uintptr_t ptr) -> std::string {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return "";
        const char* uuid = tc_display_get_uuid(d);
        return uuid ? uuid : "";
    }, nb::arg("ptr"));

    m.def("_display_set_uuid", [](uintptr_t ptr, const std::string& uuid) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) tc_display_set_uuid(d, uuid.c_str());
    }, nb::arg("ptr"), nb::arg("uuid"));

    m.def("_display_get_editor_only", [](uintptr_t ptr) -> bool {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        return d ? tc_display_get_editor_only(d) : false;
    }, nb::arg("ptr"));

    m.def("_display_set_editor_only", [](uintptr_t ptr, bool editor_only) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) tc_display_set_editor_only(d, editor_only);
    }, nb::arg("ptr"), nb::arg("editor_only"));

    m.def("_display_get_enabled", [](uintptr_t ptr) -> bool {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        return d ? tc_display_get_enabled(d) : false;
    }, nb::arg("ptr"));

    m.def("_display_set_enabled", [](uintptr_t ptr, bool enabled) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) tc_display_set_enabled(d, enabled);
    }, nb::arg("ptr"), nb::arg("enabled"));

    m.def("_display_get_surface", [](uintptr_t ptr) -> uintptr_t {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return 0;
        tc_render_surface* s = tc_display_get_surface(d);
        return reinterpret_cast<uintptr_t>(s);
    }, nb::arg("ptr"));

    m.def("_display_get_size", [](uintptr_t ptr) -> std::tuple<int, int> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        int w = 0, h = 0;
        if (d) tc_display_get_size(d, &w, &h);
        return std::make_tuple(w, h);
    }, nb::arg("ptr"));

    m.def("_display_add_viewport", [](uintptr_t display_ptr, std::tuple<uint32_t, uint32_t> vh) {
        tc_display* d = reinterpret_cast<tc_display*>(display_ptr);
        if (d) tc_display_add_viewport(d, tuple_to_vh(vh));
    }, nb::arg("display_ptr"), nb::arg("viewport_handle"));

    m.def("_display_remove_viewport", [](uintptr_t display_ptr, std::tuple<uint32_t, uint32_t> vh) {
        tc_display* d = reinterpret_cast<tc_display*>(display_ptr);
        if (d) tc_display_remove_viewport(d, tuple_to_vh(vh));
    }, nb::arg("display_ptr"), nb::arg("viewport_handle"));

    m.def("_display_get_viewport_count", [](uintptr_t ptr) -> size_t {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        return d ? tc_display_get_viewport_count(d) : 0;
    }, nb::arg("ptr"));

    m.def("_display_get_first_viewport", [](uintptr_t ptr) -> std::tuple<uint32_t, uint32_t> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return std::make_tuple(0xFFFFFFFF, 0u);
        return vh_to_tuple(tc_display_get_first_viewport(d));
    }, nb::arg("ptr"));

    m.def("_display_get_viewport_at_index", [](uintptr_t ptr, size_t index) -> std::tuple<uint32_t, uint32_t> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return std::make_tuple(0xFFFFFFFF, 0u);
        return vh_to_tuple(tc_display_get_viewport_at_index(d, index));
    }, nb::arg("ptr"), nb::arg("index"));

    m.def("_display_viewport_at", [](uintptr_t ptr, float x, float y) -> std::tuple<uint32_t, uint32_t> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return std::make_tuple(0xFFFFFFFF, 0u);
        return vh_to_tuple(tc_display_viewport_at(d, x, y));
    }, nb::arg("ptr"), nb::arg("x"), nb::arg("y"));

    m.def("_display_viewport_at_screen", [](uintptr_t ptr, float px, float py) -> std::tuple<uint32_t, uint32_t> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return std::make_tuple(0xFFFFFFFF, 0u);
        return vh_to_tuple(tc_display_viewport_at_screen(d, px, py));
    }, nb::arg("ptr"), nb::arg("px"), nb::arg("py"));

    m.def("_display_update_all_pixel_rects", [](uintptr_t ptr) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) tc_display_update_all_pixel_rects(d);
    }, nb::arg("ptr"));

    m.def("_display_make_current", [](uintptr_t ptr) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) tc_display_make_current(d);
    }, nb::arg("ptr"));

    m.def("_display_swap_buffers", [](uintptr_t ptr) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) tc_display_swap_buffers(d);
    }, nb::arg("ptr"));
}

} // namespace termin
