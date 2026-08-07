#include <termin/qopt/qopt.hpp>

#include <Eigen/Core>
#include <Eigen/Sparse>

namespace termin::qopt {

    static_assert(EIGEN_WORLD_VERSION >= 3);
    static_assert(sizeof(Eigen::Index) >= sizeof(DenseIndex));

    std::string_view termin_qopt_version() noexcept {
        return "0.1.0";
    }

} // namespace termin::qopt
