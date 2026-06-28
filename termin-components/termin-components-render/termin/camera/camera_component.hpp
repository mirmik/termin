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
#include <cstdint>

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
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;

private:
    std::vector<TcViewport> viewports_;

public:
    // layer_mask is registered manually in camera_component.cpp to use kind="layer_mask".

public:
    CameraComponent();
    static void register_type();

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

} // namespace termin
