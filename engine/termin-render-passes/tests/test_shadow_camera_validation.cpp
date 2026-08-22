#include "guard_main.h"

GUARD_TEST_MAIN();

#include <limits>

#include <termin/render/shadow_camera.hpp>

namespace {

    termin::ShadowCascadeFitRequest valid_request() {
        termin::ShadowCascadeFitRequest request;
        request.view_matrix = termin::Mat44::identity();
        request.projection_matrix = termin::Mat44::identity();
        request.camera_near = 0.1f;
        request.camera_far = 100.0f;
        request.light_direction = termin::Vec3{0.0, -1.0, -1.0};
        request.cascade_near = 0.1f;
        request.cascade_far = 20.0f;
        request.shadow_map_resolution = 1024;
        request.caster_offset = 50.0f;
        return request;
    }

} // namespace

TEST_CASE("shadow cascade fitting accepts a finite contained depth range") {
    CHECK(termin::try_fit_shadow_frustum_for_cascade(valid_request()).has_value());
}

TEST_CASE("shadow cascade fitting rejects non-finite parameters") {
    const float nan = std::numeric_limits<float>::quiet_NaN();

    auto request = valid_request();
    request.camera_near = nan;
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());

    request = valid_request();
    request.cascade_far = nan;
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());

    request = valid_request();
    request.caster_offset = nan;
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());

    request = valid_request();
    request.light_direction = termin::Vec3{nan, 0.0, 0.0};
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());
}

TEST_CASE("shadow cascade fitting rejects invalid camera and cascade domains") {
    auto request = valid_request();
    request.camera_near = 0.0f;
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());

    request = valid_request();
    request.camera_far = request.camera_near;
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());

    request = valid_request();
    request.cascade_near = request.camera_near - 0.01f;
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());

    request = valid_request();
    request.cascade_far = request.camera_far + 0.01f;
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());

    request = valid_request();
    request.cascade_far = request.cascade_near;
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());

    request = valid_request();
    request.shadow_map_resolution = 0;
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());

    request = valid_request();
    request.light_direction = termin::Vec3::zero();
    CHECK_FALSE(termin::try_fit_shadow_frustum_for_cascade(request).has_value());
}
