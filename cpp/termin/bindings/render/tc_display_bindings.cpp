// tc_display_bindings.cpp - Python bindings for tc_display
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include "render/tc_display.h"
#include "render/tc_render_surface.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"

namespace nb = nanobind;

namespace termin {

void bind_tc_display(nb::module_& m) {
    // Create display with surface pointer
    m.def("_display_new", [](uintptr_t surface_ptr, const std::string& name) -> uintptr_t {
        tc_render_surface* surface = reinterpret_cast<tc_render_surface*>(surface_ptr);
        tc_display* d = tc_display_new(name.c_str(), surface);
        return reinterpret_cast<uintptr_t>(d);
    }, nb::arg("surface_ptr"), nb::arg("name"));

    // Free display
    m.def("_display_free", [](uintptr_t ptr) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) {
            tc_display_free(d);
        }
    }, nb::arg("ptr"));

    // Name property
    m.def("_display_get_name", [](uintptr_t ptr) -> std::string {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return "";
        const char* name = tc_display_get_name(d);
        return name ? name : "";
    }, nb::arg("ptr"));

    m.def("_display_set_name", [](uintptr_t ptr, const std::string& name) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) {
            tc_display_set_name(d, name.c_str());
        }
    }, nb::arg("ptr"), nb::arg("name"));

    // UUID property
    m.def("_display_get_uuid", [](uintptr_t ptr) -> std::string {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return "";
        const char* uuid = tc_display_get_uuid(d);
        return uuid ? uuid : "";
    }, nb::arg("ptr"));

    m.def("_display_set_uuid", [](uintptr_t ptr, const std::string& uuid) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) {
            tc_display_set_uuid(d, uuid.c_str());
        }
    }, nb::arg("ptr"), nb::arg("uuid"));

    // Editor only property
    m.def("_display_get_editor_only", [](uintptr_t ptr) -> bool {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        return d ? tc_display_get_editor_only(d) : false;
    }, nb::arg("ptr"));

    m.def("_display_set_editor_only", [](uintptr_t ptr, bool editor_only) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) {
            tc_display_set_editor_only(d, editor_only);
        }
    }, nb::arg("ptr"), nb::arg("editor_only"));

    // Enabled property
    m.def("_display_get_enabled", [](uintptr_t ptr) -> bool {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        return d ? tc_display_get_enabled(d) : false;
    }, nb::arg("ptr"));

    m.def("_display_set_enabled", [](uintptr_t ptr, bool enabled) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) {
            tc_display_set_enabled(d, enabled);
        }
    }, nb::arg("ptr"), nb::arg("enabled"));

    // Surface property
    m.def("_display_get_surface", [](uintptr_t ptr) -> uintptr_t {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return 0;
        tc_render_surface* s = tc_display_get_surface(d);
        return reinterpret_cast<uintptr_t>(s);
    }, nb::arg("ptr"));

    m.def("_display_set_surface", [](uintptr_t ptr, uintptr_t surface_ptr) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        tc_render_surface* s = reinterpret_cast<tc_render_surface*>(surface_ptr);
        if (d) {
            tc_display_set_surface(d, s);
        }
    }, nb::arg("ptr"), nb::arg("surface_ptr"));

    // Size (delegates to surface)
    m.def("_display_get_size", [](uintptr_t ptr) -> std::tuple<int, int> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        int w = 0, h = 0;
        if (d) {
            tc_display_get_size(d, &w, &h);
        }
        return std::make_tuple(w, h);
    }, nb::arg("ptr"));

    // Viewport management - using viewport handle tuples (index, generation)
    m.def("_display_add_viewport", [](uintptr_t display_ptr, std::tuple<uint32_t, uint32_t> vh) {
        tc_display* d = reinterpret_cast<tc_display*>(display_ptr);
        if (d) {
            tc_viewport_handle handle;
            handle.index = std::get<0>(vh);
            handle.generation = std::get<1>(vh);
            tc_display_add_viewport(d, handle);
        }
    }, nb::arg("display_ptr"), nb::arg("viewport_handle"));

    m.def("_display_remove_viewport", [](uintptr_t display_ptr, std::tuple<uint32_t, uint32_t> vh) {
        tc_display* d = reinterpret_cast<tc_display*>(display_ptr);
        if (d) {
            tc_viewport_handle handle;
            handle.index = std::get<0>(vh);
            handle.generation = std::get<1>(vh);
            tc_display_remove_viewport(d, handle);
        }
    }, nb::arg("display_ptr"), nb::arg("viewport_handle"));

    m.def("_display_get_viewport_count", [](uintptr_t ptr) -> size_t {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        return d ? tc_display_get_viewport_count(d) : 0;
    }, nb::arg("ptr"));

    m.def("_display_get_first_viewport", [](uintptr_t ptr) -> std::tuple<uint32_t, uint32_t> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return std::make_tuple(0xFFFFFFFF, 0u);
        tc_viewport_handle vh = tc_display_get_first_viewport(d);
        return std::make_tuple(vh.index, vh.generation);
    }, nb::arg("ptr"));

    m.def("_display_get_viewport_at_index", [](uintptr_t ptr, size_t index) -> std::tuple<uint32_t, uint32_t> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return std::make_tuple(0xFFFFFFFF, 0u);
        tc_viewport_handle vh = tc_display_get_viewport_at_index(d, index);
        return std::make_tuple(vh.index, vh.generation);
    }, nb::arg("ptr"), nb::arg("index"));

    // Viewport lookup by coordinates
    m.def("_display_viewport_at", [](uintptr_t ptr, float x, float y) -> std::tuple<uint32_t, uint32_t> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return std::make_tuple(0xFFFFFFFF, 0u);
        tc_viewport_handle vh = tc_display_viewport_at(d, x, y);
        return std::make_tuple(vh.index, vh.generation);
    }, nb::arg("ptr"), nb::arg("x"), nb::arg("y"));

    m.def("_display_viewport_at_screen", [](uintptr_t ptr, float px, float py) -> std::tuple<uint32_t, uint32_t> {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (!d) return std::make_tuple(0xFFFFFFFF, 0u);
        tc_viewport_handle vh = tc_display_viewport_at_screen(d, px, py);
        return std::make_tuple(vh.index, vh.generation);
    }, nb::arg("ptr"), nb::arg("px"), nb::arg("py"));

    // Update all pixel rects
    m.def("_display_update_all_pixel_rects", [](uintptr_t ptr) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) {
            tc_display_update_all_pixel_rects(d);
        }
    }, nb::arg("ptr"));

    // Delegated methods
    m.def("_display_make_current", [](uintptr_t ptr) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) {
            tc_display_make_current(d);
        }
    }, nb::arg("ptr"));

    m.def("_display_swap_buffers", [](uintptr_t ptr) {
        tc_display* d = reinterpret_cast<tc_display*>(ptr);
        if (d) {
            tc_display_swap_buffers(d);
        }
    }, nb::arg("ptr"));
}

} // namespace termin
