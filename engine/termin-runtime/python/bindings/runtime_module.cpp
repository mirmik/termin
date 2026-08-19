#include "python_game_application.hpp"

#include <nanobind/nanobind.h>

namespace nb = nanobind;

NB_MODULE(_runtime_native, module) {
    module.doc() = "Optional Python adapters for the native Termin runtime";
    termin::runtime::python::bind_game_application(module);
}
