#include <termin/qopt/qp_types.hpp>

namespace termin::qopt {

std::string_view qp_status_name(QpStatus status) noexcept {
  switch (status) {
  case QpStatus::Optimal:
    return "optimal";
  case QpStatus::Infeasible:
    return "infeasible";
  case QpStatus::Unbounded:
    return "unbounded";
  case QpStatus::NonConvex:
    return "non_convex";
  case QpStatus::InvalidInput:
    return "invalid_input";
  case QpStatus::NumericalFailure:
    return "numerical_failure";
  }
  return "unknown";
}

std::string_view qp_diagnostic_name(QpDiagnostic diagnostic) noexcept {
  switch (diagnostic) {
  case QpDiagnostic::None:
    return "none";
  case QpDiagnostic::NullData:
    return "null_data";
  case QpDiagnostic::InvalidStride:
    return "invalid_stride";
  case QpDiagnostic::DimensionMismatch:
    return "dimension_mismatch";
  case QpDiagnostic::NonFiniteInput:
    return "non_finite_input";
  case QpDiagnostic::NonSymmetricHessian:
    return "non_symmetric_hessian";
  case QpDiagnostic::InvalidTolerance:
    return "invalid_tolerance";
  case QpDiagnostic::OverlappingOutputs:
    return "overlapping_outputs";
  case QpDiagnostic::InconsistentEqualities:
    return "inconsistent_equalities";
  case QpDiagnostic::LinearDescentInNullspace:
    return "linear_descent_in_nullspace";
  case QpDiagnostic::NegativeCurvature:
    return "negative_curvature";
  case QpDiagnostic::DecompositionFailure:
    return "decomposition_failure";
  case QpDiagnostic::ResidualTooLarge:
    return "residual_too_large";
  }
  return "unknown";
}

} // namespace termin::qopt
