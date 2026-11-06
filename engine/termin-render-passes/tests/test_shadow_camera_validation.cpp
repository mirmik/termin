#include "guard_main.h"

GUARD_TEST_MAIN();

#include <limits>
#include <cmath>

#include <termin/render/shadow_camera.hpp>
#include <termin/render/render_item_culling.hpp>

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

    tc_render_item bounds_around(const termin::Vec3& position, double radius = 0.25) {
        tc_render_item item{};
        item.kind = TC_RENDER_ITEM_KIND_MESH;
        item.bounds_state = TC_RENDER_ITEM_BOUNDS_VALID;
        item.world_bounds = {{position.x - radius, position.y - radius, position.z - radius},
                             {position.x + radius, position.y + radius, position.z + radius}};
        return item;
    }

    bool visible(const termin::RenderItemCullingView& view, const tc_render_item& item) {
        termin::RenderItemCullingCounters counters;
        return view.visible(item, counters);
    }

} // namespace

TEST_CASE("shadow cameras use right X forward Y and up Z") {
    using namespace termin;
    for (const Vec3 direction : {Vec3::unit_y(), Vec3::unit_x(), Vec3::unit_z(), Vec3{0.3, -0.7, -0.5}}) {
        const Vec3 forward = direction.normalized();
        const Vec3 reference_up = std::abs(forward.dot(Vec3::unit_z())) > 0.99 ? Vec3::unit_y() : Vec3::unit_z();
        const Vec3 right = forward.cross(reference_up).normalized();
        const Vec3 up = right.cross(forward);
        const ShadowCameraParams params{direction, Bounds2f{-2, -3, 6, 5}, 20, 1, 21, {4, 5, 6}};
        const Vec3 eye = shadow_camera_position(params);
        const Mat44f view = build_shadow_view_matrix(params);
        const Mat44f rotation = build_light_rotation_matrix(direction);
        const Vec3f mapped_eye = view.transform_point(eye.to_float());
        CHECK(mapped_eye.norm() < 3e-6f);
        const Vec3f mapped_forward = rotation.transform_direction(forward.to_float());
        const Vec3f mapped_right = rotation.transform_direction(right.to_float());
        const Vec3f mapped_up = rotation.transform_direction(up.to_float());
        CHECK((mapped_forward - Vec3f{0, 1, 0}).norm() < 3e-6f);
        CHECK((mapped_right - Vec3f{1, 0, 0}).norm() < 3e-6f);
        CHECK((mapped_up - Vec3f{0, 0, 1}).norm() < 3e-6f);

        const Mat44f projection = build_shadow_projection_matrix(params);
        const Mat44f canonical = Mat44f::orthographic(-2, 6, -3, 5, 1, 21);
        for (int index = 0; index < 16; ++index) {
            CHECK(projection.data[index] == canonical.data[index]);
        }
        const Mat44f clip = compute_light_space_matrix(params);
        const Vec3f near_corner = clip.transform_point((eye - right * 2 - up * 3 + forward).to_float());
        const Vec3f far_corner = clip.transform_point((eye + right * 6 + up * 5 + forward * 21).to_float());
        CHECK((near_corner - Vec3f{-1, 1, 0}).norm() < 3e-6f);
        CHECK((far_corner - Vec3f{1, -1, 1}).norm() < 3e-6f);
    }
}

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

TEST_CASE("cascade light volumes retain upstream casters behind the primary camera during motion") {
    using namespace termin;
    set_render_item_culling_enabled(true);
    // Light travels forward along the camera axis. This upstream caster is
    // outside the main camera but shadows the receiver at y=12.
    const Vec3 caster_position{0, -3, 0};
    const Vec3 receiver_position{0, 12, 0};
    const auto caster = bounds_around(caster_position);
    const auto receiver = bounds_around(receiver_position);
    const auto unrelated = bounds_around({10000, 12, 0});

    for (int cascade_count : {2, 3, 4}) {
        for (double camera_y : {0.0, 2.0, 4.0}) {
            for (float camera_near : {0.25f, 1.0f}) {
                ShadowCascadeFitRequest request;
                request.camera_near = camera_near;
                request.camera_far = 60;
                request.view_matrix = Mat44::look_at({0.25, camera_y, 0}, {0.25, camera_y + 1, 0});
                request.projection_matrix = Mat44::perspective(1.2, 1.3, camera_near, request.camera_far);
                request.light_direction = Vec3::unit_y();
                request.caster_offset = 100;
                request.shadow_map_resolution = 256;
                const RenderItemCullingView primary(request.view_matrix.to_float(), request.projection_matrix.to_float());
                CHECK_FALSE(visible(primary, caster));
                CHECK(visible(primary, receiver));
                const auto splits = compute_cascade_splits(camera_near, 48, cascade_count, 0.5);
                for (int cascade = 0; cascade < cascade_count; ++cascade) {
                    request.cascade_near = splits[cascade];
                    request.cascade_far = splits[cascade + 1];
                    const auto fit = try_fit_shadow_frustum_for_cascade(request);
                    REQUIRE(fit.has_value());
                    const Mat44f view = build_shadow_view_matrix(*fit);
                    const Mat44f projection = build_shadow_projection_matrix(*fit);
                    const RenderItemCullingView shadow(view, projection);
                    CHECK(visible(shadow, caster));
                    CHECK_FALSE(visible(shadow, unrelated));
                    const Mat44f light_clip = projection * view;
                    const Vec3f caster_clip = light_clip.transform_point(caster_position.to_float());
                    const Vec3f receiver_clip = light_clip.transform_point(receiver_position.to_float());
                    // Same shadow texel, shallower caster depth: removing this
                    // caster on primary-camera visibility would erase a shadow.
                    CHECK(std::abs(caster_clip.x - receiver_clip.x) < 1e-6f);
                    CHECK(std::abs(caster_clip.y - receiver_clip.y) < 1e-6f);
                    CHECK(caster_clip.z < receiver_clip.z);
                    CHECK(caster_clip.z >= 0 && caster_clip.z <= 1);

                    set_render_item_culling_enabled(false);
                    const auto unculled_fit = try_fit_shadow_frustum_for_cascade(request);
                    REQUIRE(unculled_fit.has_value());
                    const Mat44f unculled_clip = compute_light_space_matrix(*unculled_fit);
                    for (int i = 0; i < 16; ++i) {
                        CHECK(unculled_clip.data[i] == light_clip.data[i]);
                    }
                    set_render_item_culling_enabled(true);
                }
            }
        }
    }
}

TEST_CASE("caster offset and rotated camera bounds use the fitted light volume") {
    using namespace termin;
    set_render_item_culling_enabled(true);
    for (Vec3 direction : {Vec3::unit_y(), Vec3::unit_x(), Vec3{-0.6, 0.8, 0}}) {
        const Vec3 eye{10, 20, 30};
        const Vec3 caster_position = eye - direction * 3;
        const auto caster = bounds_around(caster_position);
        ShadowCascadeFitRequest request;
        request.camera_near = 1;
        request.camera_far = 40;
        request.cascade_near = 1;
        request.cascade_far = 12;
        request.view_matrix = Mat44::look_at(eye, eye + direction);
        request.projection_matrix = Mat44::perspective(1.2, 1, 1, 40);
        request.light_direction = direction;
        request.shadow_map_resolution = 256;
        request.caster_offset = 100;
        const RenderItemCullingView primary(request.view_matrix.to_float(), request.projection_matrix.to_float());
        CHECK_FALSE(visible(primary, caster));
        const auto fit = try_fit_shadow_frustum_for_cascade(request);
        REQUIRE(fit.has_value());
        CHECK(visible(RenderItemCullingView(build_shadow_view_matrix(*fit), build_shadow_projection_matrix(*fit)), caster));
        request.caster_offset = 0;
        const auto without_offset = try_fit_shadow_frustum_for_cascade(request);
        REQUIRE(without_offset.has_value());
        CHECK_FALSE(visible(RenderItemCullingView(build_shadow_view_matrix(*without_offset),
                                                build_shadow_projection_matrix(*without_offset)), caster));
    }
}
