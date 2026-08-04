#include <termin/physics_qopt/point_kinematics3d.hpp>

#include <cstdio>
#include <utility>

namespace termin::physics_qopt
{

    std::string_view point_kinematics3d_diagnostic_name(
        PointKinematics3DDiagnostic diagnostic) noexcept
    {
        switch (diagnostic)
        {
        case PointKinematics3DDiagnostic::None:
            return "none";
        case PointKinematics3DDiagnostic::InvalidModel:
            return "invalid_model";
        case PointKinematics3DDiagnostic::InvalidLink:
            return "invalid_link";
        case PointKinematics3DDiagnostic::NonFinitePoint:
            return "non_finite_point";
        case PointKinematics3DDiagnostic::NonFiniteForce:
            return "non_finite_force";
        case PointKinematics3DDiagnostic::InvalidOutput:
            return "invalid_output";
        case PointKinematics3DDiagnostic::InternalFailure:
            return "internal_failure";
        }
        return "unknown";
    }

    std::size_t PointKinematics3D::dof_count() const noexcept
    {
        return linear_jacobian_world_storage.size() / 3;
    }

    bool PointKinematics3D::is_static() const noexcept
    {
        return linear_jacobian_world_storage.empty();
    }

    ConstDenseMatrixView
    PointKinematics3D::linear_jacobian_world() const noexcept
    {
        return ConstDenseMatrixView::row_major(
            linear_jacobian_world_storage.data(), 3, dof_count());
    }

    PointKinematics3DDiagnostic
    PointKinematics3D::map_force_to_generalized_effort(
        termin::Vec3 force_world,
        DenseVectorView generalized_effort) const noexcept
    {
        if (!force_world.is_finite())
        {
            std::fprintf(stderr,
                         "[termin-qopt] rejected non-finite point force\n");
            return PointKinematics3DDiagnostic::NonFiniteForce;
        }
        const std::size_t columns = dof_count();
        if (linear_jacobian_world_storage.size() != 3 * columns ||
            generalized_effort.size != columns ||
            (columns != 0 && (generalized_effort.data == nullptr ||
                              generalized_effort.stride == 0)))
        {
            std::fprintf(
                stderr, "[termin-qopt] invalid point-force transpose output\n");
            return PointKinematics3DDiagnostic::InvalidOutput;
        }

        const double force[3]{force_world.x, force_world.y, force_world.z};
        for (std::size_t column = 0; column < columns; ++column)
        {
            generalized_effort[column] = 0.0;
            for (std::size_t row = 0; row < 3; ++row)
            {
                generalized_effort[column] +=
                    linear_jacobian_world_storage[row * columns + column] *
                    force[row];
            }
        }
        return PointKinematics3DDiagnostic::None;
    }

    bool PointKinematics3DResult::ok() const noexcept
    {
        return diagnostic == PointKinematics3DDiagnostic::None;
    }

    PointKinematics3DResult
    static_point_kinematics(termin::Vec3 position_world) noexcept
    {
        if (!position_world.is_finite())
        {
            std::fprintf(stderr,
                         "[termin-qopt] rejected non-finite static point\n");
            return {{}, PointKinematics3DDiagnostic::NonFinitePoint};
        }
        PointKinematics3D value;
        value.position_world = position_world;
        return {std::move(value), PointKinematics3DDiagnostic::None};
    }

} // namespace termin::physics_qopt
