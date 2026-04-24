#include <nanobind/nanobind.h>
#include "sdl_bindings.hpp"

namespace nb = nanobind;

NB_MODULE(_platform_native, m) {
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
}
