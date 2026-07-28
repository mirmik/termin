#include <termin/qopt/subspaces.hpp>

#include "qp_internal.hpp"

#include <Eigen/QR>
#include <Eigen/SVD>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>

namespace termin::qopt {
namespace {

using namespace detail;

struct ComputedNullspace {
  NullspaceResult result;
  Matrix basis;
};

[[nodiscard]] NullspaceResult nullspace_failure(
    QpStatus status, QpDiagnostic diagnostic
) noexcept {
  NullspaceResult result;
  result.status = status;
  result.diagnostic = diagnostic;
  return result;
}

[[nodiscard]] ComputedNullspace compute(
    ConstDenseMatrixView source, NullspaceOptions options
) {
  ComputedNullspace output;
  const Matrix matrix = copy_matrix(source);
  const Eigen::Index variables = matrix.cols();
  if (matrix.rows() == 0) {
    output.basis = Matrix::Identity(variables, variables);
    output.result.status = QpStatus::Optimal;
    output.result.rank = 0;
    output.result.nullity = static_cast<std::size_t>(variables);
  } else if (options.method == NullspaceMethod::RankRevealingQr) {
    Eigen::ColPivHouseholderQR<Matrix> qr(matrix.transpose());
    qr.setThreshold(
        scaled_tolerance(options.tolerance, matrix_linf(matrix))
    );
    const Eigen::Index rank = qr.rank();
    const Matrix orthogonal =
        qr.householderQ() * Matrix::Identity(variables, variables);
    output.basis = orthogonal.rightCols(variables - rank);
    output.result.status = QpStatus::Optimal;
    output.result.rank = static_cast<std::size_t>(rank);
    output.result.nullity =
        static_cast<std::size_t>(variables - rank);
  } else {
    Eigen::JacobiSVD<Matrix> svd(
        matrix, Eigen::ComputeFullU | Eigen::ComputeFullV
    );
    if (svd.info() != Eigen::Success) {
      output.result = nullspace_failure(
          QpStatus::NumericalFailure,
          QpDiagnostic::DecompositionFailure
      );
      return output;
    }
    const Vector singular_values = svd.singularValues();
    const double threshold = scaled_tolerance(
        options.tolerance, linf(singular_values)
    );
    Eigen::Index rank = 0;
    for (Eigen::Index index = 0; index < singular_values.size(); ++index) {
      if (singular_values[index] > threshold) {
        ++rank;
      }
    }
    output.basis = svd.matrixV().rightCols(variables - rank);
    output.result.status = QpStatus::Optimal;
    output.result.rank = static_cast<std::size_t>(rank);
    output.result.nullity =
        static_cast<std::size_t>(variables - rank);
  }

  const Matrix residual = matrix * output.basis;
  const Matrix orthogonality =
      output.basis.transpose() * output.basis
      - Matrix::Identity(output.basis.cols(), output.basis.cols());
  output.result.residual_linf = matrix_linf(residual);
  output.result.orthogonality_linf = matrix_linf(orthogonality);
  return output;
}

[[nodiscard]] QpDiagnostic validate(
    ConstDenseMatrixView matrix,
    DenseMatrixView destination,
    NullspaceOptions options
) noexcept {
  const QpDiagnostic source_diagnostic = validate_matrix(matrix);
  if (source_diagnostic != QpDiagnostic::None) {
    return source_diagnostic;
  }
  const QpDiagnostic destination_diagnostic =
      validate_matrix(ConstDenseMatrixView{destination});
  if (destination_diagnostic != QpDiagnostic::None) {
    return destination_diagnostic;
  }
  if (
      destination.rows != matrix.columns
      || destination.columns != matrix.columns
  ) {
    return QpDiagnostic::DimensionMismatch;
  }
  if (!valid_tolerance(options.tolerance)) {
    return QpDiagnostic::InvalidTolerance;
  }
  if (!finite(matrix)) {
    return QpDiagnostic::NonFiniteInput;
  }
  return QpDiagnostic::None;
}

} // namespace

NullspaceResult write_nullspace_basis(
    ConstDenseMatrixView matrix,
    DenseMatrixView destination,
    NullspaceOptions options
) noexcept {
  const QpDiagnostic diagnostic = validate(matrix, destination, options);
  if (diagnostic != QpDiagnostic::None) {
    return nullspace_failure(QpStatus::InvalidInput, diagnostic);
  }
  try {
    const ComputedNullspace computed = compute(matrix, options);
    if (computed.result.status != QpStatus::Optimal) {
      return computed.result;
    }
    for (std::size_t row = 0; row < destination.rows; ++row) {
      for (std::size_t column = 0; column < destination.columns; ++column) {
        destination(row, column) =
            column < computed.result.nullity
            ? computed.basis(
                  static_cast<Eigen::Index>(row),
                  static_cast<Eigen::Index>(column)
              )
            : 0.0;
      }
    }
    return computed.result;
  } catch (const std::exception& error) {
    std::fprintf(
        stderr, "[termin-qopt] nullspace basis failed: %s\n", error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr, "[termin-qopt] nullspace basis failed with unknown exception\n"
    );
  }
  return nullspace_failure(
      QpStatus::NumericalFailure, QpDiagnostic::DecompositionFailure
  );
}

NullspaceResult write_nullspace_projector(
    ConstDenseMatrixView matrix,
    DenseMatrixView destination,
    NullspaceOptions options
) noexcept {
  const QpDiagnostic diagnostic = validate(matrix, destination, options);
  if (diagnostic != QpDiagnostic::None) {
    return nullspace_failure(QpStatus::InvalidInput, diagnostic);
  }
  try {
    const ComputedNullspace computed = compute(matrix, options);
    if (computed.result.status != QpStatus::Optimal) {
      return computed.result;
    }
    const Matrix projector =
        computed.basis * computed.basis.transpose();
    for (std::size_t row = 0; row < destination.rows; ++row) {
      for (std::size_t column = 0; column < destination.columns; ++column) {
        destination(row, column) = projector(
            static_cast<Eigen::Index>(row),
            static_cast<Eigen::Index>(column)
        );
      }
    }
    return computed.result;
  } catch (const std::exception& error) {
    std::fprintf(
        stderr,
        "[termin-qopt] nullspace projector failed: %s\n",
        error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr,
        "[termin-qopt] nullspace projector failed with unknown exception\n"
    );
  }
  return nullspace_failure(
      QpStatus::NumericalFailure, QpDiagnostic::DecompositionFailure
  );
}

} // namespace termin::qopt
