#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.h>

extern "C" {
#include "core/tc_camera_capability.h"
#include "tc_value.h"
}

#include <termin/camera/camera_component.hpp>
#include <termin/entity/component_registry.hpp>

namespace termin {

    namespace {

        void register_camera_component_inspect_fields(tc::InspectFacetBuilder& builder);

    } // namespace

    // Camera capability vtable callback
    static bool camera_cap_get_data(tc_component* self, double aspect_override, tc_camera_data* out) {
        if (!self || !out)
            return false;
        CxxComponent* cxx = CxxComponent::from_tc(self);
        if (!cxx)
            return false;
        CameraComponent* cam = static_cast<CameraComponent*>(cxx);

        Mat44 view = cam->get_view_matrix();
        Mat44 proj =
            (aspect_override > 0) ? cam->compute_projection_matrix(aspect_override) : cam->get_projection_matrix();
        Vec3 pos = cam->get_position();

        std::memcpy(out->view, view.data, sizeof(out->view));
        std::memcpy(out->projection, proj.data, sizeof(out->projection));
        out->position[0] = pos.x;
        out->position[1] = pos.y;
        out->position[2] = pos.z;
        out->near_clip = cam->near_clip;
        out->far_clip = cam->far_clip;
        out->layer_mask = cam->layer_mask;
        out->render_category_mask = cam->render_category_mask;
        return true;
    }

    static const tc_camera_vtable g_camera_vtable = {
        .get_camera_data = camera_cap_get_data,
    };

    CameraComponent::CameraComponent()
        : CxxComponent("CameraComponent") {
        tc_camera_capability_attach(&_c, &g_camera_vtable, this);
    }

    std::string CameraComponent::get_projection_type_str() const {
        return projection_type == CameraProjection::Perspective ? "perspective" : "orthographic";
    }

    void CameraComponent::set_projection_type_str(const std::string& type) {
        if (type == "orthographic") {
            projection_type = CameraProjection::Orthographic;
        } else {
            projection_type = CameraProjection::Perspective;
        }
    }

    std::string CameraComponent::get_fov_mode_str() const {
        switch (fov_mode) {
        case FovMode::FixHorizontal:
            return "FixHorizontal";
        case FovMode::FixVertical:
            return "FixVertical";
        case FovMode::FixBoth:
            return "FixBoth";
        default:
            return "FixHorizontal";
        }
    }

    void CameraComponent::set_fov_mode_str(const std::string& mode) {
        if (mode == "FixVertical") {
            fov_mode = FovMode::FixVertical;
        } else if (mode == "FixBoth") {
            fov_mode = FovMode::FixBoth;
        } else {
            fov_mode = FovMode::FixHorizontal;
        }
    }

    double CameraComponent::get_fov_x_degrees() const {
        return fov_x * 180.0 / M_PI;
    }

    void CameraComponent::set_fov_x_degrees(double deg) {
        fov_x = deg * M_PI / 180.0;
    }

    double CameraComponent::get_fov_y_degrees() const {
        return fov_y * 180.0 / M_PI;
    }

    void CameraComponent::set_fov_y_degrees(double deg) {
        fov_y = deg * M_PI / 180.0;
    }

    void CameraComponent::set_aspect(double a) {
        aspect = a;
    }

    Mat44 CameraComponent::get_view_matrix() const {
        if (!entity().valid()) {
            return Mat44::identity();
        }

        const GeneralTransform3 transform = entity().transform();
        Pose3 pose(transform.global_rotation(), transform.global_position());
        Pose3 inv_pose = pose.inverse();
        return inv_pose.as_mat44();
    }

    Mat44 CameraComponent::get_projection_matrix() const {
        return compute_projection_matrix(aspect);
    }

    Mat44 CameraComponent::compute_projection_matrix(double aspect_override) const {
        if (projection_type == CameraProjection::Orthographic) {
            double top = ortho_size;
            double bottom = -ortho_size;
            double right = ortho_size * aspect_override;
            double left = -right;
            return Mat44::orthographic(left, right, bottom, top, near_clip, far_clip);
        }

        double safe_aspect = std::max(1e-6, aspect_override);
        switch (fov_mode) {
        case FovMode::FixHorizontal: {
            double computed_fov_y = 2.0 * std::atan(std::tan(fov_x * 0.5) / safe_aspect);
            return Mat44::perspective(computed_fov_y, safe_aspect, near_clip, far_clip);
        }
        case FovMode::FixVertical:
            return Mat44::perspective(fov_y, safe_aspect, near_clip, far_clip);
        case FovMode::FixBoth:
            return Mat44::perspective_fov_xy(fov_x, fov_y, near_clip, far_clip);
        default:
            return Mat44::perspective(fov_y, safe_aspect, near_clip, far_clip);
        }
    }

    Vec3 CameraComponent::get_position() const {
        if (!entity().valid()) {
            return Vec3::zero();
        }
        return entity().transform().global_position();
    }

    void CameraComponent::add_viewport(const TcViewport& vp) {
        if (!vp.is_valid()) {
            return;
        }
        for (auto& v : viewports_) {
            if (tc_viewport_handle_eq(v.handle_, vp.handle_)) {
                return;
            }
        }
        viewports_.push_back(vp);
    }

    void CameraComponent::remove_viewport(const TcViewport& vp) {
        viewports_.erase(
            std::remove_if(viewports_.begin(),
                           viewports_.end(),
                           [&vp](const TcViewport& v) { return tc_viewport_handle_eq(v.handle_, vp.handle_); }),
            viewports_.end());
    }

    bool CameraComponent::has_viewport(const TcViewport& vp) const {
        for (const auto& v : viewports_) {
            if (tc_viewport_handle_eq(v.handle_, vp.handle_)) {
                return true;
            }
        }
        return false;
    }

    size_t CameraComponent::viewport_count() const {
        return viewports_.size();
    }

    TcViewport CameraComponent::viewport_at(size_t index) const {
        return index < viewports_.size() ? viewports_[index] : TcViewport();
    }

    void CameraComponent::clear_viewports() {
        viewports_.clear();
    }

    void CameraComponent::on_destroy() {
        // Render targets resolve cameras from their stable scene/entity handles.
        // This reverse list is UI bookkeeping only and is not a lifetime owner.
        viewports_.clear();
    }

    void CameraComponent::on_removed() {
        viewports_.clear();
    }

    void CameraComponent::on_scene_inactive() {
        clear_viewports();
    }

    std::optional<Ray3> CameraComponent::try_screen_point_to_ray(const Vec2& screen_point,
                                                                 const Rect2& viewport,
                                                                 ScreenRayError* error) const {
        ScreenRayError failure = ScreenRayError::None;
        if (!entity().valid()) {
            failure = ScreenRayError::MissingViewTransform;
        } else if (!viewport.is_finite() || viewport.width <= 0.0 || viewport.height <= 0.0) {
            failure = ScreenRayError::InvalidViewport;
        } else {
            const double viewport_aspect = viewport.width / viewport.height;
            const Mat44 projection = compute_projection_matrix(viewport_aspect);
            const Mat44 view = get_view_matrix();
            Ray3 ray;
            if (try_unproject_screen_ray(projection, view, screen_point, viewport, ray, &failure)) {
                if (error) {
                    *error = ScreenRayError::None;
                }
                return ray;
            }
        }

        if (error) {
            *error = failure;
        }
        tc_log_error("[CameraComponent] Failed to project screen point to ray: %s", screen_ray_error_message(failure));
        return std::nullopt;
    }

    std::optional<ProjectedScreenPoint> CameraComponent::try_project_world_point(const Vec3& world_point,
                                                                                 const Rect2& viewport,
                                                                                 ScreenRayError* error) const {
        ScreenRayError failure = ScreenRayError::None;
        if (!entity().valid()) {
            failure = ScreenRayError::MissingViewTransform;
        } else if (!viewport.is_finite() || viewport.width <= 0.0 || viewport.height <= 0.0) {
            failure = ScreenRayError::InvalidViewport;
        } else {
            const double viewport_aspect = viewport.width / viewport.height;
            const Mat44 projection = compute_projection_matrix(viewport_aspect);
            const Mat44 view = get_view_matrix();
            ProjectedScreenPoint projected;
            if (termin::try_project_world_point(projection, view, world_point, viewport, projected, &failure)) {
                if (error) {
                    *error = ScreenRayError::None;
                }
                return projected;
            }
        }

        if (error) {
            *error = failure;
        }
        tc_log_error("[CameraComponent] Failed to project world point to screen: %s",
                     screen_ray_error_message(failure));
        return std::nullopt;
    }

    namespace {

        void register_fov_mode_field(tc::InspectFacetBuilder& builder) {
            tc::InspectFieldInfo info;
            info.type_name = "CameraComponent";
            info.path = "fov_mode";
            info.label = "FOV Mode";
            info.kind = "string";
            info.choices.push_back({"FixHorizontal", "Fix Horizontal"});
            info.choices.push_back({"FixVertical", "Fix Vertical"});
            info.choices.push_back({"FixBoth", "Fix Both"});
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<CameraComponent*>(obj);
                return tc_value_string(c->get_fov_mode_str().c_str());
            };
            info.setter = [](void* obj, tc_value value, void*) -> bool {
                auto* c = static_cast<CameraComponent*>(obj);
                if (value.type == TC_VALUE_STRING && value.data.s) {
                    c->set_fov_mode_str(value.data.s);
                    return true;
                }
                return false;
            };
            (void)builder.add_field(std::move(info));
        }

        void register_camera_layer_mask_field(tc::InspectFacetBuilder& builder) {
            tc::InspectFieldInfo info;
            info.type_name = "CameraComponent";
            info.path = "layer_mask";
            info.label = "Layers";
            info.kind = "layer_mask";
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<CameraComponent*>(obj);
                char buf[32];
                snprintf(buf, sizeof(buf), "0x%llx", (unsigned long long)c->layer_mask);
                return tc_value_string(buf);
            };
            info.setter = [](void* obj, tc_value value, void*) -> bool {
                auto* c = static_cast<CameraComponent*>(obj);
                if (value.type == TC_VALUE_STRING && value.data.s) {
                    c->layer_mask = strtoull(value.data.s, nullptr, 0);
                    return true;
                } else if (value.type == TC_VALUE_INT) {
                    c->layer_mask = static_cast<uint64_t>(value.data.i);
                    return true;
                }
                return false;
            };
            (void)builder.add_field(std::move(info));
        }

        void register_camera_render_category_mask_field(tc::InspectFacetBuilder& builder) {
            tc::InspectFieldInfo info;
            info.type_name = "CameraComponent";
            info.path = "render_category_mask";
            info.label = "Render Categories";
            info.kind = "string";
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<CameraComponent*>(obj);
                char buf[32];
                snprintf(buf, sizeof(buf), "0x%llx", (unsigned long long)c->render_category_mask);
                return tc_value_string(buf);
            };
            info.setter = [](void* obj, tc_value value, void*) -> bool {
                auto* c = static_cast<CameraComponent*>(obj);
                if (value.type == TC_VALUE_STRING && value.data.s) {
                    c->render_category_mask = strtoull(value.data.s, nullptr, 0);
                    return true;
                } else if (value.type == TC_VALUE_INT) {
                    c->render_category_mask = static_cast<uint64_t>(value.data.i);
                    return true;
                }
                return false;
            };
            (void)builder.add_field(std::move(info));
        }

        void register_camera_component_inspect_fields(tc::InspectFacetBuilder& builder) {
            tc::stage_inspect_field(builder,
                                    &CameraComponent::near_clip,
                                    "CameraComponent",
                                    "near_clip",
                                    "Near Clip",
                                    "double",
                                    0.001,
                                    10000.0,
                                    0.01);
            tc::stage_inspect_field(builder,
                                    &CameraComponent::far_clip,
                                    "CameraComponent",
                                    "far_clip",
                                    "Far Clip",
                                    "double",
                                    0.01,
                                    100000.0,
                                    1.0);
            tc::stage_inspect_field(builder,
                                    &CameraComponent::ortho_size,
                                    "CameraComponent",
                                    "ortho_size",
                                    "Ortho Size",
                                    "double",
                                    0.1,
                                    1000.0,
                                    0.5);
            builder.add_with_callbacks<CameraComponent, double>(
                "CameraComponent",
                "fov_x_degrees",
                "Horizontal FOV",
                "double",
                [](CameraComponent* c) -> double& {
                    static double deg;
                    deg = c->get_fov_x_degrees();
                    return deg;
                },
                [](CameraComponent* c, const double& val) { c->set_fov_x_degrees(val); },
                1.0,
                360.0,
                1.0);
            builder.add_with_callbacks<CameraComponent, double>(
                "CameraComponent",
                "fov_y_degrees",
                "Vertical FOV",
                "double",
                [](CameraComponent* c) -> double& {
                    static double deg;
                    deg = c->get_fov_y_degrees();
                    return deg;
                },
                [](CameraComponent* c, const double& val) { c->set_fov_y_degrees(val); },
                1.0,
                360.0,
                1.0);
            register_fov_mode_field(builder);
            register_camera_layer_mask_field(builder);
            register_camera_render_category_mask_field(builder);
        }

    } // namespace

    void CameraComponent::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<CameraComponent>(
            "CameraComponent", "termin-components-render", "CxxComponent");
        descriptor.category("Rendering");
        register_camera_component_inspect_fields(descriptor.inspect());
        (void)descriptor.commit();
    }

} // namespace termin
