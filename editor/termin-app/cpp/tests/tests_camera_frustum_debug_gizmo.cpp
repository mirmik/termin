#include "guard_main.h"

#include "termin/editor/camera_frustum_debug_gizmo.hpp"

#include <termin/camera/camera_component.hpp>
#include <termin/entity/entity.hpp>

using termin::CameraComponent;
using termin::CameraFrustumCorners;
using termin::Entity;

namespace {

    tc_camera_data camera_data_from(CameraComponent& camera) {
        tc_camera_data data = {};
        termin::Mat44 view = camera.get_view_matrix();
        termin::Mat44 projection = camera.get_projection_matrix();
        view.copy_column_major_to(data.view);
        projection.copy_column_major_to(data.projection);
        termin::Vec3 position = camera.get_position();
        data.position[0] = position.x;
        data.position[1] = position.y;
        data.position[2] = position.z;
        data.near_clip = camera.near_clip;
        data.far_clip = camera.far_clip;
        data.layer_mask = camera.layer_mask;
        data.render_category_mask = camera.render_category_mask;
        return data;
    }

} // namespace

TEST_CASE("Camera frustum debug computes finite perspective corners") {
    Entity camera_entity = Entity::create(Entity::standalone_pool_handle(), "frustum-camera");
    CameraComponent* camera = new CameraComponent();
    camera_entity.add_component(camera);
    camera->near_clip = 0.5;
    camera->far_clip = 10.0;
    camera->aspect = 16.0 / 9.0;

    CameraFrustumCorners corners;
    std::string error;
    REQUIRE(termin::compute_camera_frustum_corners(camera_data_from(*camera), corners, &error));
    CHECK(error.empty());

    for (const termin::Vec3& point : corners.points) {
        CHECK(point.is_finite());
    }

    tc_entity_free(camera_entity.handle());
}

TEST_CASE("Camera frustum debug rejects singular projection-view matrices") {
    tc_camera_data data = {};
    for (int i = 0; i < 16; ++i) {
        data.view[i] = 0.0;
        data.projection[i] = 0.0;
    }

    CameraFrustumCorners corners;
    for (termin::Vec3& point : corners.points) {
        point = {17.0, 18.0, 19.0};
    }
    std::string error;
    CHECK(!termin::compute_camera_frustum_corners(data, corners, &error));
    CHECK(!error.empty());
    for (const termin::Vec3& point : corners.points) {
        CHECK((point == termin::Vec3{17.0, 18.0, 19.0}));
    }
}
