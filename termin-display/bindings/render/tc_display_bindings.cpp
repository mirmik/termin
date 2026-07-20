// tc_display_bindings.cpp - Python bindings for TcDisplay
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/vector.h>

#include "termin/render/tc_display_handle.hpp"
#include "termin/platform/offscreen_render_surface.hpp"
#include "tc_render_surface_bindings.hpp"
#include "termin/viewport/tc_viewport_handle.hpp"
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"

extern "C" {
#include "render/tc_render_surface.h"
#include "render/tc_render_target.h"
#include "core/tc_scene.h"
#include "core/tc_component.h"
}

namespace nb = nanobind;

namespace termin {

static TcDisplay configured_display(
    tc_display_handle handle,
    bool editor_only,
    const std::string& uuid
) {
    if (!tc_display_handle_valid(handle)) {
        throw std::runtime_error("failed to create display");
    }
    TcDisplay display(handle);
    if (!uuid.empty()) display.set_uuid(uuid);
    display.set_editor_only(editor_only);
    return display;
}

void bind_tc_display(nb::module_& m) {
    // TcDisplay class binding
    nb::class_<TcDisplay>(m, "Display",
        "Display - render target with viewports.\n\n"
        "Wraps tc_display. Contains surface and viewport list.")

        .def(nb::init<>())

        .def("is_valid", &TcDisplay::is_valid)

        .def("destroy", &TcDisplay::destroy,
             "Explicitly destroy the native display. Python GC does not call this.")

        .def_prop_ro("handle", [](TcDisplay& self) {
            tc_display_handle handle = self.handle();
            return std::make_tuple(handle.index, handle.generation);
        }, "Stable (index, generation) display identity")

        .def_prop_ro("index", [](TcDisplay& self) { return self.handle().index; })
        .def_prop_ro("generation", [](TcDisplay& self) { return self.handle().generation; })

        .def_prop_ro("tc_input_manager_ptr", [](TcDisplay& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.input_manager());
        }, "Stable display-owned tc_input_manager endpoint")

        .def("dispatch_pointer_move", [](TcDisplay& self, double x, double y) {
            return self.dispatch_pointer_move(x, y);
        }, nb::arg("x"), nb::arg("y"))
        .def("dispatch_pointer_button",
             [](TcDisplay& self, double x, double y, int button, int action,
                int modifiers, uint32_t click_count) {
                 return self.dispatch_pointer_button(
                     x, y, button, action, modifiers, click_count);
             }, nb::arg("x"), nb::arg("y"), nb::arg("button"), nb::arg("action"),
             nb::arg("modifiers"), nb::arg("click_count") = 1)
        .def("dispatch_wheel",
             [](TcDisplay& self, double x, double y, double wheel_x,
                double wheel_y, int modifiers) {
                 return self.dispatch_wheel(x, y, wheel_x, wheel_y, modifiers);
             }, nb::arg("x"), nb::arg("y"), nb::arg("wheel_x"),
             nb::arg("wheel_y"), nb::arg("modifiers"))
        .def("dispatch_key", [](TcDisplay& self, int key, int scancode,
                                int action, int modifiers) {
            return self.dispatch_key(key, scancode, action, modifiers);
        }, nb::arg("key"), nb::arg("scancode"), nb::arg("action"), nb::arg("modifiers"))
        .def("dispatch_text", [](TcDisplay& self, uint32_t codepoint) {
            return self.dispatch_text(codepoint);
        }, nb::arg("codepoint"))

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

        .def_prop_rw("auto_remove_when_empty",
            &TcDisplay::auto_remove_when_empty,
            &TcDisplay::set_auto_remove_when_empty,
            "If True, display is auto-removed when last viewport is removed")

        // Size
        .def("get_size", [](TcDisplay& self) {
            return self.get_size();
        }, "Return display size in pixels as (width, height)")
        .def("framebuffer_size", [](TcDisplay& self) {
            return self.get_size();
        }, "Return display surface size in pixels")
        .def("resize", &TcDisplay::resize, nb::arg("width"), nb::arg("height"))
        .def("get_tgfx_color_tex_id", &TcDisplay::color_texture_id)
        .def_prop_ro("color_tex", [](TcDisplay& self) {
            return tgfx::TextureHandle{self.color_texture_id()};
        })
        .def("graphics_domain_key", &TcDisplay::graphics_domain_key)

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

        // Create viewport helper
        .def("create_viewport", [](TcDisplay& self,
                                   nb::object scene_obj,
                                   nb::object camera_obj,
                                   std::tuple<float, float, float, float> rect,
                                   const std::string& name) -> TcViewport {
            // Get scene handle
            tc_scene_handle scene_h = TC_SCENE_HANDLE_INVALID;
            if (!scene_obj.is_none()) {
                scene_h = nb::cast<tc_scene_handle>(scene_obj.attr("scene_handle")());
            }

            // Get camera component pointer
            tc_component* camera_ptr = nullptr;
            if (!camera_obj.is_none()) {
                camera_ptr = reinterpret_cast<tc_component*>(
                    nb::cast<uintptr_t>(camera_obj.attr("c_component_ptr")())
                );
            }

            // Create viewport (render target assigned separately)
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
           "Create and add new viewport")

        // Static factory
        .def_static("offscreen", [](tgfx::IRenderDevice& device, int width, int height,
                                     const std::string& name, bool editor_only,
                                     const std::string& uuid) {
            return configured_display(
                create_offscreen_display(&device, width, height, name.c_str()),
                editor_only,
                uuid);
        }, nb::arg("device"), nb::arg("width"), nb::arg("height"),
           nb::arg("name") = "Display", nb::arg("editor_only") = false,
           nb::arg("uuid") = "",
           "Create a display that exclusively owns an offscreen texture surface")

        .def_static("from_surface", [](nb::object surface_object,
                                        const std::string& name,
                                        bool editor_only,
                                        const std::string& uuid) {
            tc_render_surface* surface = create_python_render_surface(surface_object);
            if (!surface) throw std::runtime_error("failed to create Python surface adapter");
            tc_display_handle handle = tc_display_new(name.c_str(), surface);
            if (!tc_display_handle_valid(handle)) {
                tc_render_surface_delete_unowned(surface);
            }
            return configured_display(handle, editor_only, uuid);
        }, nb::arg("surface"), nb::arg("name") = "Display",
           nb::arg("editor_only") = false, nb::arg("uuid") = "",
           "Create a display and transfer ownership of a Python surface adapter")

        .def_static("from_handle", [](uint32_t index, uint32_t generation) {
            return TcDisplay::from_handle(tc_display_handle{index, generation});
        }, nb::arg("index"), nb::arg("generation"),
           "Create a non-owning display facade from generation handle")
    ;
}

} // namespace termin
