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

void FBOSurfaceRef::resize(int width, int height) {
        if (auto* s = surface()) {
            s->resize(width, height);
        }
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
        .def("make_current", &FBOSurfaceRef::make_current)
        .def("swap_buffers", &FBOSurfaceRef::swap_buffers)
        .def("should_close", &FBOSurfaceRef::should_close)
        .def("set_should_close", &FBOSurfaceRef::set_should_close, nb::arg("value"))
        .def("get_cursor_pos", &FBOSurfaceRef::get_cursor_pos)
        .def("share_group_key", &FBOSurfaceRef::share_group_key)
        .def("close", &FBOSurfaceRef::close);
}

} // namespace termin
