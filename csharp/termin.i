// SWIG interface for Termin C++ classes
%module(directors="1") termin

%{
#include "termin/geom/vec3.hpp"
#include "termin/geom/quat.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/camera/camera.hpp"
#include "tc_pass.h"
#include "tc_pipeline.h"
%}

// Use std::string
%include "std_string.i"

// Rename operators for C# compatibility
%rename(Add) operator+;
%rename(Subtract) operator-;
%rename(Multiply) operator*;
%rename(Divide) operator/;
%rename(Equals) operator==;
%rename(NotEquals) operator!=;
%rename(Negate) operator-() const;

// Ignore problematic operators
%ignore operator[];

// Vec3
namespace termin {

struct Vec3 {
    double x, y, z;

    Vec3();
    Vec3(double x, double y, double z);

    Vec3 operator+(const Vec3& v) const;
    Vec3 operator-(const Vec3& v) const;
    Vec3 operator*(double s) const;
    Vec3 operator/(double s) const;
    Vec3 operator-() const;

    bool operator==(const Vec3& v) const;
    bool operator!=(const Vec3& v) const;

    double dot(const Vec3& v) const;
    Vec3 cross(const Vec3& v) const;
    double norm() const;
    double norm_squared() const;
    Vec3 normalized() const;

    static double angle(const Vec3& a, const Vec3& b);
    static double angle_degrees(const Vec3& a, const Vec3& b);
    static Vec3 zero();
    static Vec3 unit_x();
    static Vec3 unit_y();
    static Vec3 unit_z();
};

// Quat
struct Quat {
    double x, y, z, w;

    Quat();
    Quat(double x, double y, double z, double w);

    static Quat identity();
    Quat operator*(const Quat& q) const;
    Quat conjugate() const;
    Quat inverse() const;
    double norm() const;
    Quat normalized() const;
    Vec3 rotate(const Vec3& v) const;
    Vec3 inverse_rotate(const Vec3& v) const;

    static Quat from_axis_angle(const Vec3& axis, double angle);
    static Quat look_rotation(const Vec3& forward, const Vec3& up = Vec3::unit_z());
    static Quat slerp(const Quat& a, const Quat& b, double t);
    static Quat from_rotation_matrix(const double* m);
    void to_matrix(double* m) const;
};

// Mat44
struct Mat44 {
    double data[16];

    Mat44();

    double* ptr();
    const double* ptr() const;

    static Mat44 identity();
    static Mat44 zero();

    Mat44 operator*(const Mat44& b) const;
    Vec3 transform_point(const Vec3& p) const;
    Vec3 transform_direction(const Vec3& d) const;
    Mat44 transposed() const;
    Mat44 inverse() const;

    static Mat44 translation(const Vec3& t);
    static Mat44 scale(const Vec3& s);
    static Mat44 scale(double s);
    static Mat44 rotation(const Quat& q);
    static Mat44 rotation_axis_angle(const Vec3& axis, double angle);
    static Mat44 perspective(double fov_y, double aspect, double near, double far);
    static Mat44 orthographic(double left, double right, double bottom, double top, double near, double far);
    static Mat44 look_at(const Vec3& eye, const Vec3& target, const Vec3& up = Vec3::unit_z());
    static Mat44 compose(const Vec3& t, const Quat& r, const Vec3& s);

    Vec3 get_translation() const;
    Vec3 get_scale() const;
    Mat44 with_translation(const Vec3& t) const;
};

// CameraProjection enum
enum class CameraProjection {
    Perspective,
    Orthographic
};

// Camera - ignore redundant set_* methods since properties have setters
%ignore termin::Camera::set_aspect;
%ignore termin::Camera::set_fov;
%ignore termin::Camera::set_fov_deg;
%ignore termin::Camera::get_fov_deg;

struct Camera {
    CameraProjection projection_type;
    double near;
    double far;
    double fov_y;
    double aspect;
    double ortho_left;
    double ortho_right;
    double ortho_bottom;
    double ortho_top;

    Camera();

    static Camera perspective(double fov_y_rad, double aspect, double near = 0.1, double far = 100.0);
    static Camera perspective_deg(double fov_y_deg, double aspect, double near = 0.1, double far = 100.0);
    static Camera orthographic(double left, double right, double bottom, double top, double near = 0.1, double far = 100.0);

    Mat44 projection_matrix() const;
    static Mat44 view_matrix(const Vec3& position, const Quat& rotation);
    static Mat44 view_matrix_look_at(const Vec3& eye, const Vec3& target, const Vec3& up = Vec3::unit_z());
};

} // namespace termin

// ============================================================================
// Pass Registry API (C)
// ============================================================================

// Opaque types
typedef struct tc_pass tc_pass;
typedef struct tc_pipeline tc_pipeline;

// Pass registry
bool tc_pass_registry_has(const char* type_name);
tc_pass* tc_pass_registry_create(const char* type_name);
size_t tc_pass_registry_type_count(void);
const char* tc_pass_registry_type_at(size_t index);

// Pass properties
void tc_pass_set_name(tc_pass* p, const char* name);
void tc_pass_set_enabled(tc_pass* p, bool enabled);

// Pipeline
tc_pipeline* tc_pipeline_create(const char* name);
void tc_pipeline_destroy(tc_pipeline* pipeline);
void tc_pipeline_add_pass(tc_pipeline* pipeline, tc_pass* pass);
size_t tc_pipeline_pass_count(tc_pipeline* pipeline);
tc_pass* tc_pipeline_pass_at(tc_pipeline* pipeline, size_t index);
