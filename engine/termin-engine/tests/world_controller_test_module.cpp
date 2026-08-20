#include <nanobind/nanobind.h>

#include "world_controller_bindings.hpp"

NB_MODULE(_world_controller_test_native, module) {
    module.doc() = "Focused WorldController binding test module";
    termin::python::bind_world_controller(module);
}
