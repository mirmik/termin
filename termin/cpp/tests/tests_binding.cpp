#include <nanobind/nanobind.h>
#include "guard/guard.h"

namespace nb = nanobind;

NB_MODULE(_cpp_tests, m)
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
        nb::arg("filter") = "",
        nb::arg("verbose") = false);
}
