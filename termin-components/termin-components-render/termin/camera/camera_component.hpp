#pragma once

#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/export.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/pose3.hpp>
#include <termin/viewport/tc_viewport_handle.hpp>

#include <string>
#include <utility>
#include <vector>

#include <termin/camera/camera.hpp>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

enum class FovMode {
    FixHorizontal,
    FixVertical,
    FixBoth
};

class ENTITY_API CameraComponent : public CxxComponent {
public:
    CameraProjection projection_type = CameraProjection::Perspective;
    double near_clip = 0.1;
    double far_clip = 100.0;
    FovMode fov_mode = FovMode::FixHorizontal;
    double fov_x = M_PI / 3.0;
    double fov_y = M_PI / 4.0;
    double aspect = 1.0;
    double ortho_size = 5.0;

private:
    std::vector<TcViewport> viewports_;

public:
    INSPECT_FIELD(CameraComponent, near_clip, "Near Clip", "double", 0.001, 10000.0, 0.01)
    INSPECT_FIELD(CameraComponent, far_clip, "Far Clip", "double", 0.01, 100000.0, 1.0)
    INSPECT_FIELD(CameraComponent, ortho_size, "Ortho Size", "double", 0.1, 1000.0, 0.5)

public:
    CameraComponent();

    std::string get_projection_type_str() const;
    void set_projection_type_str(const std::string& type);
    std::string get_fov_mode_str() const;
    void set_fov_mode_str(const std::string& mode);
    double get_fov_x_degrees() const;
    void set_fov_x_degrees(double deg);
    double get_fov_y_degrees() const;
    void set_fov_y_degrees(double deg);
    double get_fov_degrees() const { return get_fov_x_degrees(); }
    void set_fov_degrees(double deg) { set_fov_x_degrees(deg); }
    void set_aspect(double a);
    Mat44 get_view_matrix() const;
    Mat44 get_projection_matrix() const;
    Mat44 compute_projection_matrix(double aspect_override) const;
    Vec3 get_position() const;
    void add_viewport(const TcViewport& vp);
    void remove_viewport(const TcViewport& vp);
    bool has_viewport(const TcViewport& vp) const;
    size_t viewport_count() const;
    TcViewport viewport_at(size_t index) const;
    void clear_viewports();
    void on_destroy() override;
    void on_removed() override;
    void on_scene_inactive() override;
    std::pair<Vec3, Vec3> screen_point_to_ray(double x, double y, int vp_x, int vp_y, int vp_w, int vp_h) const;
};

INSPECT_FIELD_CALLBACK(CameraComponent, double, fov_x_degrees, "Horizontal FOV", "double",
    [](CameraComponent* c) -> double& {
        static double deg;
        deg = c->get_fov_x_degrees();
        return deg;
    },
    [](CameraComponent* c, const double& val) { c->set_fov_x_degrees(val); },
    1.0, 360.0, 1.0)

INSPECT_FIELD_CALLBACK(CameraComponent, double, fov_y_degrees, "Vertical FOV", "double",
    [](CameraComponent* c) -> double& {
        static double deg;
        deg = c->get_fov_y_degrees();
        return deg;
    },
    [](CameraComponent* c, const double& val) { c->set_fov_y_degrees(val); },
    1.0, 360.0, 1.0)

} // namespace termin
