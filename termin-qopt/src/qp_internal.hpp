#pragma once

#include <termin/qopt/dense_views.hpp>
#include <termin/qopt/equality_qp.hpp>
#include <termin/qopt/qp_types.hpp>

#include <Eigen/Core>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>

namespace termin::qopt::detail {

using Matrix = Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic>;
using Vector = Eigen::Matrix<double, Eigen::Dynamic, 1>;

[[nodiscard]] QpSolveResult solve_equality_qp_spd_first(
    EqualityQpProblemView problem, EqualityQpSolutionView solution,
    QpTolerance tolerance) noexcept;

[[nodiscard]] inline QpSolveResult
failure(QpStatus status, QpDiagnostic diagnostic,
        std::size_t iterations = 0) noexcept {
  QpSolveResult result;
  result.status = status;
  result.diagnostic = diagnostic;
  result.iterations = iterations;
  return result;
}

[[nodiscard]] inline double linf(const Vector &value) noexcept {
  return value.size() == 0 ? 0.0 : value.cwiseAbs().maxCoeff();
}

[[nodiscard]] inline double matrix_linf(const Matrix &value) noexcept {
  return value.size() == 0 ? 0.0 : value.cwiseAbs().maxCoeff();
}

[[nodiscard]] inline double scaled_tolerance(QpTolerance tolerance,
                                             double scale) noexcept {
  return tolerance.absolute + tolerance.relative * std::max(1.0, scale);
}

[[nodiscard]] inline bool valid_tolerance(QpTolerance tolerance) noexcept {
  return std::isfinite(tolerance.absolute) &&
         std::isfinite(tolerance.relative) &&
         std::isfinite(tolerance.symmetry) && tolerance.absolute >= 0.0 &&
         tolerance.relative >= 0.0 && tolerance.symmetry >= 0.0;
}

[[nodiscard]] inline QpDiagnostic
validate_vector(ConstDenseVectorView view) noexcept {
  if (view.size == 0) {
    return QpDiagnostic::None;
  }
  if (view.data == nullptr) {
    return QpDiagnostic::NullData;
  }
  return view.stride == 0 ? QpDiagnostic::InvalidStride : QpDiagnostic::None;
}

[[nodiscard]] inline QpDiagnostic
validate_vector(DenseVectorView view) noexcept {
  return validate_vector(ConstDenseVectorView{view});
}

[[nodiscard]] inline QpDiagnostic
validate_matrix(ConstDenseMatrixView view) noexcept {
  if (view.rows == 0 || view.columns == 0) {
    return QpDiagnostic::None;
  }
  if (view.data == nullptr) {
    return QpDiagnostic::NullData;
  }
  return view.row_stride == 0 || view.column_stride == 0
             ? QpDiagnostic::InvalidStride
             : QpDiagnostic::None;
}

[[nodiscard]] inline bool finite(ConstDenseVectorView view) noexcept {
  for (std::size_t index = 0; index < view.size; ++index) {
    if (!std::isfinite(view[index])) {
      return false;
    }
  }
  return true;
}

[[nodiscard]] inline bool finite(ConstDenseMatrixView view) noexcept {
  for (std::size_t row = 0; row < view.rows; ++row) {
    for (std::size_t column = 0; column < view.columns; ++column) {
      if (!std::isfinite(view(row, column))) {
        return false;
      }
    }
  }
  return true;
}

[[nodiscard]] inline Vector copy_vector(ConstDenseVectorView view) {
  Vector result(static_cast<Eigen::Index>(view.size));
  for (std::size_t index = 0; index < view.size; ++index) {
    result[static_cast<Eigen::Index>(index)] = view[index];
  }
  return result;
}

[[nodiscard]] inline Matrix copy_matrix(ConstDenseMatrixView view) {
  Matrix result(static_cast<Eigen::Index>(view.rows),
                static_cast<Eigen::Index>(view.columns));
  for (std::size_t row = 0; row < view.rows; ++row) {
    for (std::size_t column = 0; column < view.columns; ++column) {
      result(static_cast<Eigen::Index>(row),
             static_cast<Eigen::Index>(column)) = view(row, column);
    }
  }
  return result;
}

inline void copy_to_view(const Vector &source,
                         DenseVectorView destination) noexcept {
  for (std::size_t index = 0; index < destination.size; ++index) {
    destination[index] = source[static_cast<Eigen::Index>(index)];
  }
}

[[nodiscard]] inline ConstDenseVectorView view(const Vector &value) noexcept {
  return {value.data(), static_cast<std::size_t>(value.size()), 1};
}

[[nodiscard]] inline DenseVectorView view(Vector &value) noexcept {
  return {value.data(), static_cast<std::size_t>(value.size()), 1};
}

[[nodiscard]] inline ConstDenseMatrixView view(const Matrix &value) noexcept {
  return ConstDenseMatrixView::column_major(
      value.data(), static_cast<std::size_t>(value.rows()),
      static_cast<std::size_t>(value.cols()));
}

struct AddressInterval {
  std::uintptr_t first = 0;
  std::uintptr_t last = 0;
  bool empty = true;
};

[[nodiscard]] inline AddressInterval
address_interval(DenseVectorView value) noexcept {
  if (value.size == 0 || value.data == nullptr) {
    return {};
  }

  constexpr std::uintptr_t max_address =
      std::numeric_limits<std::uintptr_t>::max();
  const std::uintptr_t base = reinterpret_cast<std::uintptr_t>(value.data);
  const std::uintptr_t stride_magnitude =
      value.stride >= 0 ? static_cast<std::uintptr_t>(value.stride)
                        : static_cast<std::uintptr_t>(-(value.stride + 1)) + 1;
  const std::uintptr_t element_count = value.size - 1;
  if (stride_magnitude > max_address / sizeof(double) ||
      element_count > max_address / (stride_magnitude * sizeof(double))) {
    return {0, max_address, false};
  }

  const std::uintptr_t span = element_count * stride_magnitude * sizeof(double);
  const std::uintptr_t tail = sizeof(double) - 1;
  if (value.stride >= 0) {
    if (span > max_address - base || tail > max_address - base - span) {
      return {0, max_address, false};
    }
    return {base, base + span + tail, false};
  }
  if (span > base || tail > max_address - base) {
    return {0, max_address, false};
  }
  return {base - span, base + tail, false};
}

[[nodiscard]] inline bool overlaps(DenseVectorView left,
                                   DenseVectorView right) noexcept {
  const AddressInterval left_interval = address_interval(left);
  const AddressInterval right_interval = address_interval(right);
  return !left_interval.empty && !right_interval.empty &&
         left_interval.first <= right_interval.last &&
         right_interval.first <= left_interval.last;
}

} // namespace termin::qopt::detail
