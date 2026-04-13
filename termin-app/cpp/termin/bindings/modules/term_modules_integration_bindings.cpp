#include "term_modules_integration_bindings.hpp"

#include <nanobind/stl/filesystem.h>

#include <termin_modules/module_runtime.hpp>

#include "termin/modules/term_modules_integration.hpp"

namespace nb = nanobind;

namespace termin {

void bind_term_modules_integration(nb::module_& m) {
    nb::module_::import_("termin_modules");

    nb::class_<TermModulesIntegration>(m, "TermModulesIntegration")
        .def(nb::init<>())
        .def("set_environment", &TermModulesIntegration::set_environment, nb::arg("environment"))
        .def_prop_ro(
            "environment",
            &TermModulesIntegration::environment,
            nb::rv_policy::reference_internal
        )
        .def("configure_runtime", &TermModulesIntegration::configure_runtime, nb::arg("runtime"));
}

} // namespace termin
