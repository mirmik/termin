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

uintptr_t FBOSurfaceRef::graphics_domain_key() const {
        if (auto* s = surface()) {
            return tc_render_surface_get_graphics_domain_key(s->tc_surface());
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
        .def_prop_ro("color_tex", &FBOSurfaceRef::color_tex)
        .def_prop_ro("depth_tex", &FBOSurfaceRef::depth_tex)
        .def_prop_ro("tc_surface_ptr", &FBOSurfaceRef::tc_surface_ptr)
        .def("get_tgfx_color_tex_id", &FBOSurfaceRef::get_tgfx_color_tex_id)
        .def("graphics_domain_key", &FBOSurfaceRef::graphics_domain_key)
        .def("close", &FBOSurfaceRef::close);
}

} // namespace termin
