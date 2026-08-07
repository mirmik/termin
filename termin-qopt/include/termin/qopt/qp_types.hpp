#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <string_view>

#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

    enum class QpStatus : std::uint8_t {
        Optimal,
        Infeasible,
        Unbounded,
        NonConvex,
        InvalidInput,
        NumericalFailure,
    };

    enum class QpDiagnostic : std::uint8_t {
        None,
        NullData,
        InvalidStride,
        DimensionMismatch,
        NonFiniteInput,
        NonSymmetricHessian,
        InvalidTolerance,
        OverlappingOutputs,
        InconsistentEqualities,
        LinearDescentInNullspace,
        NegativeCurvature,
        DecompositionFailure,
        ResidualTooLarge,
        InvalidOptions,
        InvalidBounds,
        InvalidWarmStart,
        InconsistentInequalities,
        IterationLimit,
    };

    struct QpTolerance {
        double absolute = 1e-12;
        double relative = 1e-12;
        double symmetry = 1e-10;
    };

    struct QpSolveResult {
        QpStatus status = QpStatus::InvalidInput;
        QpDiagnostic diagnostic = QpDiagnostic::None;
        double stationarity_linf = std::numeric_limits<double>::infinity();
        double equality_linf = std::numeric_limits<double>::infinity();
        double inequality_linf = 0.0;
        double dual_linf = 0.0;
        double complementarity_linf = 0.0;
        std::size_t constraint_rank = 0;
        std::size_t reduced_hessian_rank = 0;
        std::size_t active_set_size = 0;
        std::size_t iterations = 0;
    };

    [[nodiscard]] TERMIN_QOPT_API std::string_view qp_status_name(QpStatus status) noexcept;
    [[nodiscard]] TERMIN_QOPT_API std::string_view qp_diagnostic_name(QpDiagnostic diagnostic) noexcept;

} // namespace termin::qopt
