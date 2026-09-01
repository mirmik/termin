#include <nanobind/nanobind.h>
#include <nanobind/stl/pair.h>

#include <tcbase/tc_log.hpp>

#include "termin/platform/backend_window.hpp"

#ifdef TERMIN_DISPLAY_HAS_SDL
#include "sdl_bindings.hpp"
#endif

namespace nb = nanobind;

namespace termin {

#ifndef TERMIN_PLATFORM_LEGACY_ONLY
    void bind_backend_window(nb::module_& m) {
        nb::class_<BackendWindow>(m, "BackendWindow")
            .def("window_size", &BackendWindow::window_size)
            .def("framebuffer_size", &BackendWindow::framebuffer_size)
            .def_prop_ro("content_scale", &BackendWindow::content_scale);
        nb::class_<BackendWindowSystem>(m, "BackendWindowSystem");
    }
#endif

} // namespace termin

NB_MODULE(_platform_native, m) {
    m.attr("HAS_SDL") = nb::bool_(false);
#ifndef TERMIN_PLATFORM_LEGACY_ONLY
    termin::bind_backend_window(m);
#endif

#ifdef TERMIN_DISPLAY_HAS_SDL
    m.attr("HAS_SDL") = nb::bool_(true);

#ifdef TERMIN_PLATFORM_LEGACY_ONLY
    nb::module_::import_("termin.window._window_native");
#endif

    // BackendWindow::present() takes tgfx::TextureHandle and the windowed
    // session binding returns tgfx::GraphicsHost — both are
    // registered in _tgfx_native. Force-import so nanobind can resolve
    // those cross-module types the first time Python calls into the
    // window wrapper. Failure (tgfx not on sys.path) is non-fatal —
    // the rest of the SDL bindings stay usable.
    try {
        nb::module_::import_("termin.graphics._graphics_native");
    } catch (const std::exception& e) {
        tc::Log::debug("[platform] Failed to import termin.graphics._graphics_native: %s (non-fatal, SDL bindings remain usable)",
                       e.what());
    }

    termin::bind_sdl(m);
#endif
}
