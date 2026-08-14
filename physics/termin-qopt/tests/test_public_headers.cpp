#include <termin/qopt/qopt.hpp>

#include "test_check.hpp"

#if defined(EIGEN_WORLD_VERSION)
#error "termin-qopt public headers must not expose Eigen headers"
#endif

int main() {
    TERMIN_QOPT_CHECK(termin::qopt::termin_qopt_version() == "0.1.0");
    return 0;
}
