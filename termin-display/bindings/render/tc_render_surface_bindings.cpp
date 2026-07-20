// Python adapter for the narrow tc_render_surface texture-output ABI.
#include <nanobind/nanobind.h>
#include <nanobind/stl/tuple.h>

#include "render/tc_render_surface.h"
#include "tc_render_surface_bindings.hpp"
#include <tcbase/tc_log.hpp>

namespace nb = nanobind;

namespace termin {
namespace {

nb::object surface_object(tc_render_surface* surface) {
    return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(surface->body));
}

void python_surface_get_size(tc_render_surface* surface, int* width, int* height) {
    if (width) *width = 0;
    if (height) *height = 0;
    if (!surface || !surface->body) return;
    nb::gil_scoped_acquire gil;
    try {
        auto [w, h] = nb::cast<std::tuple<int, int>>(
            surface_object(surface).attr("framebuffer_size")());
        if (width) *width = w;
        if (height) *height = h;
    } catch (const std::exception& error) {
        tc::Log::error("python render surface framebuffer_size failed: %s", error.what());
    }
}

bool python_surface_resize(tc_render_surface* surface, int width, int height) {
    if (!surface || !surface->body) return false;
    nb::gil_scoped_acquire gil;
    try {
        bool resized = nb::cast<bool>(surface_object(surface).attr("resize")(width, height));
        if (resized) tc_render_surface_notify_resize(surface, width, height);
        return resized;
    } catch (const std::exception& error) {
        tc::Log::error("python render surface resize failed: %s", error.what());
        return false;
    }
}

uint32_t python_surface_get_color_texture_id(tc_render_surface* surface) {
    if (!surface || !surface->body) return 0;
    nb::gil_scoped_acquire gil;
    try {
        return nb::cast<uint32_t>(
            surface_object(surface).attr("get_tgfx_color_tex_id")());
    } catch (const std::exception& error) {
        tc::Log::error("python render surface color texture query failed: %s", error.what());
        return 0;
    }
}

uintptr_t python_surface_get_graphics_domain_key(tc_render_surface* surface) {
    if (!surface || !surface->body) return 0;
    nb::gil_scoped_acquire gil;
    try {
        return nb::cast<uintptr_t>(
            surface_object(surface).attr("graphics_domain_key")());
    } catch (const std::exception& error) {
        tc::Log::error("python render surface graphics domain query failed: %s", error.what());
        return 0;
    }
}

void python_surface_destroy(tc_render_surface* surface) {
    if (!surface || !surface->body) return;
    nb::gil_scoped_acquire gil;
    Py_DECREF(reinterpret_cast<PyObject*>(surface->body));
    surface->body = nullptr;
}

const tc_render_surface_vtable python_surface_vtable = {
    .get_size = python_surface_get_size,
    .resize = python_surface_resize,
    .get_color_texture_id = python_surface_get_color_texture_id,
    .get_graphics_domain_key = python_surface_get_graphics_domain_key,
    .destroy = python_surface_destroy,
};

} // namespace

tc_render_surface* create_python_render_surface(nb::object python_surface) {
    PyObject* body = python_surface.ptr();
    Py_INCREF(body);
    tc_render_surface* surface = tc_render_surface_new_external(
        body,
        &python_surface_vtable,
        sizeof(python_surface_vtable),
        TC_RENDER_SURFACE_ABI_VERSION);
    if (!surface) Py_DECREF(body);
    return surface;
}

void bind_tc_render_surface(nb::module_& module) {
    (void)module;
}

} // namespace termin
