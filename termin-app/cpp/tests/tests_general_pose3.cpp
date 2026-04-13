#include "guard/guard.h"
#include "termin/geom/general_pose3.hpp"
#include <cmath>

using guard::Approx;
using termin::GeneralPose3;
using termin::Quat;
using termin::Vec3;

TEST_CASE("GeneralPose3 identity and inverse")
{
    GeneralPose3 id = GeneralPose3::identity();
    Vec3 p{1.0, 2.0, -3.0};
    Vec3 t = id.transform_point(p);
    CHECK_EQ(t.x, p.x);
    CHECK_EQ(t.y, p.y);
    CHECK_EQ(t.z, p.z);

    GeneralPose3 inv = id.inverse();
    Vec3 back = inv.transform_point(t);
    CHECK_EQ(back.x, Approx(p.x).epsilon(1e-12));
    CHECK_EQ(back.y, Approx(p.y).epsilon(1e-12));
    CHECK_EQ(back.z, Approx(p.z).epsilon(1e-12));
}

TEST_CASE("GeneralPose3 compose with scale")
{
    GeneralPose3 parent(
        Quat::identity(),
        Vec3{1.0, 0.0, 0.0},
        Vec3{2.0, 2.0, 2.0});

    GeneralPose3 child(
        Quat::identity(),
        Vec3{0.5, 0.0, 0.0},
        Vec3{1.0, 1.0, 1.0});

    GeneralPose3 world = parent * child;

    // Translation should include parent offset + rotated (scaled) child offset
    CHECK_EQ(world.lin.x, Approx(1.0 + 2.0 * 0.5).epsilon(1e-12));
    CHECK_EQ(world.lin.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(world.lin.z, Approx(0.0).epsilon(1e-12));

    // Scale propagates multiplicatively
    CHECK_EQ(world.scale.x, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(world.scale.y, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(world.scale.z, Approx(2.0).epsilon(1e-12));
}

TEST_CASE("GeneralPose3 transform and inverse")
{
    const double half_pi = std::acos(-1.0) * 0.5;
    GeneralPose3 pose(
        Quat::from_axis_angle(Vec3::unit_z(), half_pi),
        Vec3{1.0, 0.0, 0.0},
        Vec3{2.0, 1.0, 1.0});

    Vec3 p_local{1.0, 0.0, 0.0};
    Vec3 p_world = pose.transform_point(p_local);
    // Rotation 90 deg around Z: (1,0,0) -> (0,1,0), then scale (2,1,1) is applied before rotation
    CHECK_EQ(p_world.x, Approx(1.0).epsilon(1e-12));
    CHECK_EQ(p_world.y, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(p_world.z, Approx(0.0).epsilon(1e-12));

    Vec3 back = pose.inverse_transform_point(p_world);
    CHECK_EQ(back.x, Approx(p_local.x).epsilon(1e-12));
    CHECK_EQ(back.y, Approx(p_local.y).epsilon(1e-12));
    CHECK_EQ(back.z, Approx(p_local.z).epsilon(1e-12));
}
