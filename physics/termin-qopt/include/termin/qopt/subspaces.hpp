#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>

#include <termin/qopt/dense_views.hpp>
#include <termin/qopt/qp_types.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

    enum class NullspaceMethod : std::uint8_t {
        RankRevealingQr,
        Svd,
    };

    struct NullspaceOptions {
        NullspaceMethod method = NullspaceMethod::RankRevealingQr;
        QpTolerance tolerance;
    };

    struct NullspaceResult {
        QpStatus status = QpStatus::InvalidInput;
        QpDiagnostic diagnostic = QpDiagnostic::None;
        std::size_t rank = 0;
        std::size_t nullity = 0;
        double residual_linf = std::numeric_limits<double>::infinity();
        double orthogonality_linf = std::numeric_limits<double>::infinity();
    };

    // destination must be an n x n matrix, where n = matrix.columns. The first
    // result.nullity columns contain an orthonormal basis; remaining columns are
    // zeroed. This fixed-capacity contract avoids exposing an owning matrix type.
    [[nodiscard]] TERMIN_QOPT_API NullspaceResult write_nullspace_basis(ConstDenseMatrixView matrix,
                                                                        DenseMatrixView destination,
                                                                        NullspaceOptions options = {}) noexcept;

    [[nodiscard]] TERMIN_QOPT_API NullspaceResult write_nullspace_projector(ConstDenseMatrixView matrix,
                                                                            DenseMatrixView destination,
                                                                            NullspaceOptions options = {}) noexcept;

} // namespace termin::qopt
