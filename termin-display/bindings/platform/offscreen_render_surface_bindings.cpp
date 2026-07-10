#include <nanobind/nanobind.h>
#include <nanobind/stl/pair.h>

#include "offscreen_render_surface_bindings.hpp"
#include "tgfx2/i_render_device.hpp"

namespace nb = nanobind;

namespace termin {

FBOSurfaceRef::FBOSurfaceRef(tgfx::IRenderDevice& device, int width, int height)
    : handle_(offscreen_render_surface_create(&device, width, height)) {}

FBOSurfaceRef::FBOSurfaceRef(OffscreenRenderSurfaceHandle handle)
    : handle_(handle) {}

bool FBOSurfaceRef::is_valid() const {
        return offscreen_render_surface_handle_valid(handle_);
    }

OffscreenRenderSurface* FBOSurfaceRef::surface() const {
        return offscreen_render_surface_get(handle_);
    }

bool FBOSurfaceRef::resize(int width, int height) {
    if (width <= 0 || height <= 0) {
        return false;
    }
    if (auto* s = surface()) {
        s->resize(width, height);
        return true;
    }
    return false;
}

std::pair<int, int> FBOSurfaceRef::framebuffer_size() const {
        if (auto* s = surface()) {
            return s->size();
        }
        return {0, 0};
    }

std::pair<int, int> FBOSurfaceRef::window_size() const {
        return framebuffer_size();
    }

tgfx::TextureHandle FBOSurfaceRef::color_tex() const {
        if (auto* s = surface()) {
            return s->color_tex();
        }
        return {};
    }

tgfx::TextureHandle FBOSurfaceRef::depth_tex() const {
        if (auto* s = surface()) {
            return s->depth_tex();
        }
        return {};
    }

uintptr_t FBOSurfaceRef::tc_surface_ptr() const {
        if (auto* s = surface()) {
            return reinterpret_cast<uintptr_t>(s->tc_surface());
        }
        return 0;
    }

uint32_t FBOSurfaceRef::get_tgfx_color_tex_id() const {
        if (auto* s = surface()) {
            return s->color_tex().id;
        }
        return 0;
    }

uint32_t FBOSurfaceRef::get_framebuffer_id() const {
        return 0;
    }

void FBOSurfaceRef::set_input_manager(uintptr_t input_manager_ptr) {
        if (auto* s = surface()) {
            s->set_input_manager(reinterpret_cast<tc_input_manager*>(input_manager_ptr));
        }
    }

bool FBOSurfaceRef::dispatch_pointer_move(double x, double y) {
    if (auto* s = surface()) {
        if (tc_input_manager* manager = tc_render_surface_get_input_manager(s->tc_surface())) {
            tc_input_manager_on_mouse_move(manager, x, y);
            return true;
        }
    }
    return false;
}

bool FBOSurfaceRef::dispatch_pointer_button(int button, int action, int modifiers,
                                            uint32_t click_count) {
    if (auto* s = surface()) {
        if (tc_input_manager* manager = tc_render_surface_get_input_manager(s->tc_surface())) {
            tc_input_manager_on_mouse_button(manager, button, action, modifiers, click_count);
            return true;
        }
    }
    return false;
}

bool FBOSurfaceRef::dispatch_scroll(double x, double y, int modifiers) {
    if (auto* s = surface()) {
        if (tc_input_manager* manager = tc_render_surface_get_input_manager(s->tc_surface())) {
            tc_input_manager_on_scroll(manager, x, y, modifiers);
            return true;
        }
    }
    return false;
}

bool FBOSurfaceRef::dispatch_key(int key, int scancode, int action, int modifiers) {
    if (auto* s = surface()) {
        if (tc_input_manager* manager = tc_render_surface_get_input_manager(s->tc_surface())) {
            tc_input_manager_on_key(manager, key, scancode, action, modifiers);
            return true;
        }
    }
    return false;
}

bool FBOSurfaceRef::dispatch_text(uint32_t codepoint) {
    if (auto* s = surface()) {
        if (tc_input_manager* manager = tc_render_surface_get_input_manager(s->tc_surface())) {
            tc_input_manager_on_char(manager, codepoint);
            return true;
        }
    }
    return false;
}

void FBOSurfaceRef::make_current() {}
void FBOSurfaceRef::swap_buffers() {}
bool FBOSurfaceRef::should_close() const { return false; }
void FBOSurfaceRef::set_should_close(bool value) { (void)value; }
std::pair<double, double> FBOSurfaceRef::get_cursor_pos() const { return {0.0, 0.0}; }

uintptr_t FBOSurfaceRef::share_group_key() const {
        if (auto* s = surface()) {
            return tc_render_surface_share_group_key(s->tc_surface());
        }
        return 0;
    }

bool FBOSurfaceRef::close() {
        return offscreen_render_surface_destroy(handle_);
    }

void bind_offscreen_render_surface(nb::module_& m) {
    nb::class_<FBOSurfaceRef>(m, "FBOSurface")
        .def(nb::init<tgfx::IRenderDevice&, int, int>(),
             nb::arg("device"), nb::arg("width"), nb::arg("height"))
        .def("is_valid", &FBOSurfaceRef::is_valid)
        .def("resize", &FBOSurfaceRef::resize, nb::arg("width"), nb::arg("height"))
        .def("framebuffer_size", &FBOSurfaceRef::framebuffer_size)
        .def("window_size", &FBOSurfaceRef::window_size)
        .def_prop_ro("color_tex", &FBOSurfaceRef::color_tex)
        .def_prop_ro("depth_tex", &FBOSurfaceRef::depth_tex)
        .def_prop_ro("tc_surface_ptr", &FBOSurfaceRef::tc_surface_ptr)
        .def("get_tgfx_color_tex_id", &FBOSurfaceRef::get_tgfx_color_tex_id)
        .def("get_framebuffer_id", &FBOSurfaceRef::get_framebuffer_id)
        .def("set_input_manager", &FBOSurfaceRef::set_input_manager, nb::arg("input_manager_ptr"))
        .def("dispatch_pointer_move", &FBOSurfaceRef::dispatch_pointer_move, nb::arg("x"),
             nb::arg("y"))
        .def("dispatch_pointer_button", &FBOSurfaceRef::dispatch_pointer_button, nb::arg("button"),
             nb::arg("action"), nb::arg("modifiers"), nb::arg("click_count") = 1)
        .def("dispatch_scroll", &FBOSurfaceRef::dispatch_scroll, nb::arg("x"), nb::arg("y"),
             nb::arg("modifiers"))
        .def("dispatch_key", &FBOSurfaceRef::dispatch_key, nb::arg("key"), nb::arg("scancode"),
             nb::arg("action"), nb::arg("modifiers"))
        .def("dispatch_text", &FBOSurfaceRef::dispatch_text, nb::arg("codepoint"))
        .def("make_current", &FBOSurfaceRef::make_current)
        .def("swap_buffers", &FBOSurfaceRef::swap_buffers)
        .def("should_close", &FBOSurfaceRef::should_close)
        .def("set_should_close", &FBOSurfaceRef::set_should_close, nb::arg("value"))
        .def("get_cursor_pos", &FBOSurfaceRef::get_cursor_pos)
        .def("share_group_key", &FBOSurfaceRef::share_group_key)
        .def("close", &FBOSurfaceRef::close);
}

} // namespace termin
