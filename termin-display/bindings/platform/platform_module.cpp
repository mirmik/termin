#include <nanobind/nanobind.h>

#include "termin/platform/backend_window.hpp"

#ifdef TERMIN_DISPLAY_HAS_SDL
#include "sdl_bindings.hpp"
#endif

namespace nb = nanobind;

namespace termin {

void bind_backend_window(nb::module_& m) {
    nb::class_<BackendWindow>(m, "BackendWindow");
}

} // namespace termin

NB_MODULE(_platform_native, m) {
    m.attr("HAS_SDL") = nb::bool_(false);
    termin::bind_backend_window(m);

#ifdef TERMIN_DISPLAY_HAS_SDL
    m.attr("HAS_SDL") = nb::bool_(true);

    // BackendWindow::device() returns tgfx::IRenderDevice* and
    // BackendWindow::present() takes tgfx::TextureHandle — both are
    // registered in _tgfx_native. Force-import so nanobind can resolve
    // those cross-module types the first time Python calls into the
    // window wrapper. Failure (tgfx not on sys.path) is non-fatal —
    // the rest of the SDL bindings stay usable.
    try {
        nb::module_::import_("tgfx._tgfx_native");
    } catch (const std::exception&) {
        // pass
    }

    termin::bind_sdl(m);
#endif
}
