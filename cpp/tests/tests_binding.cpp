#include <pybind11/pybind11.h>
#include "guard/guard.h"

namespace py = pybind11;

PYBIND11_MODULE(_cpp_tests, m)
{
    m.doc() = "C++ test runner for guard-based tests";
    m.def(
        "run",
        [](const char *filter, bool verbose) {
            if (verbose)
            {
                guard::test::set_verbose(true);
            }
            int rc = guard::test::run_all(filter && filter[0] ? filter : nullptr);
            if (rc != 0)
            {
                throw std::runtime_error("C++ test suite failed");
            }
            return rc;
        },
        py::arg("filter") = "",
        py::arg("verbose") = false);
}
