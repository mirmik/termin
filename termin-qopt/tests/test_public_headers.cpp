#include <termin/qopt/qopt.hpp>

#include <cassert>

#if defined(EIGEN_WORLD_VERSION)
#  error "termin-qopt public headers must not expose Eigen headers"
#endif

int main() {
    assert(termin::qopt::termin_qopt_version() == "0.1.0");
    return 0;
}
