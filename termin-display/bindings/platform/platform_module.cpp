#include <nanobind/nanobind.h>
#include "sdl_bindings.hpp"

namespace nb = nanobind;

NB_MODULE(_platform_native, m) {
    termin::bind_sdl(m);
}
