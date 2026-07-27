#pragma once

#include <string_view>

#include <termin/qopt/dense_views.hpp>
#include <termin/qopt/equality_qp.hpp>
#include <termin/qopt/qp_types.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt {

[[nodiscard]] TERMIN_QOPT_API std::string_view termin_qopt_version() noexcept;

} // namespace termin::qopt
