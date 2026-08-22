#include "guard_main.h"

#include <cmath>
#include <limits>

#include <components/mesh_component.hpp>
#include <tcbase/tc_log.h>

namespace {

    int error_log_count = 0;

    void capture_log(tc_log_level level, const char*) {
        if (level == TC_LOG_ERROR) {
            ++error_log_count;
        }
    }

    struct LogCapture {
        LogCapture() {
            error_log_count = 0;
            tc_log_set_callback(capture_log);
        }

        ~LogCapture() {
            tc_log_set_callback(nullptr);
        }
    };

} // namespace

TEST_CASE("mesh offset Euler angles preserve multi-axis XYZ composition") {
    using namespace termin;

    MeshComponent component;
    component.mesh_offset_enabled = true;
    component.mesh_offset_position = {1.0, -2.0, 3.0};
    component.mesh_offset_euler = {90.0, 90.0, 0.0};
    component.mesh_offset_scale = {2.0, 3.0, 4.0};

    const Mat44f expected =
        Mat44f::compose(Vec3{1.0, -2.0, 3.0}, Quat{0.5, 0.5, -0.5, 0.5}, Vec3{2.0, 3.0, 4.0});
    const Mat44f actual = component.get_mesh_offset_matrix();

    for (int column = 0; column < 4; ++column) {
        for (int row = 0; row < 4; ++row) {
            CHECK(std::abs(actual(column, row) - expected(column, row)) <= 1.0e-6F);
        }
    }
}

TEST_CASE("mesh offset rejects serialized non-finite Euler values and exposes invalid public state") {
    using namespace termin;

    MeshComponent component;
    component.mesh_offset_enabled = true;
    component.mesh_offset_euler = {10.0, 20.0, 30.0};

    {
        LogCapture capture;
        component.set_mesh_offset_euler({std::numeric_limits<double>::infinity(), 0.0, 0.0});
        CHECK(error_log_count > 0);
    }
    CHECK(component.mesh_offset_euler.x == guard::Approx(10.0));
    CHECK(component.mesh_offset_euler.y == guard::Approx(20.0));
    CHECK(component.mesh_offset_euler.z == guard::Approx(30.0));

    component.mesh_offset_euler = {std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0};
    Mat44f invalid_matrix;
    {
        LogCapture capture;
        invalid_matrix = component.get_mesh_offset_matrix();
        CHECK(error_log_count > 0);
    }
    CHECK_FALSE(invalid_matrix.is_finite());
}

GUARD_TEST_MAIN();
