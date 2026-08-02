#pragma once

#include <string_view>

#include <termin/qopt/active_set_qp.hpp>
#include <termin/qopt/articulation3d.hpp>
#include <termin/qopt/articulation3d_motor.hpp>
#include <termin/qopt/block_assembly.hpp>
#include <termin/qopt/dense_views.hpp>
#include <termin/qopt/dynamics.hpp>
#include <termin/qopt/equality_qp.hpp>
#include <termin/qopt/hqp.hpp>
#include <termin/qopt/multibody2d.hpp>
#include <termin/qopt/multibody3d.hpp>
#include <termin/qopt/qp_types.hpp>
#include <termin/qopt/subspaces.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt
{

    [[nodiscard]] TERMIN_QOPT_API std::string_view termin_qopt_version() noexcept;

} // namespace termin::qopt
