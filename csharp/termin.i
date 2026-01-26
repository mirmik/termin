// SWIG interface for Termin C++ classes
%module(directors="1") termin

%{
#include "termin/geom/vec3.hpp"
#include "termin/geom/quat.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/camera/camera.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/render_engine.hpp"
#include "termin/render/mesh_renderer.hpp"
#include "termin/render/color_pass.hpp"
#include "termin/render/depth_pass.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/entity/component.hpp"
#include "tc_pass.h"
#include "tc_pipeline.h"
#include "tc_opengl.h"
#include "tc_component.h"
%}

// Use std::string
%include "std_string.i"

// ============================================================================
// C# Component External Body Support
// ============================================================================

// C API for external body management
%{
// These are called from C# via P/Invoke to set up reference counting
static void csharp_body_incref(void* body) {
    // body is GCHandle.ToIntPtr() - prevent GC by allocating another handle
    // Actually, we use Normal handle which already prevents GC
    // So incref is a no-op, decref frees the handle
}

static void csharp_body_decref(void* body) {
    // body is GCHandle.ToIntPtr() - free it to allow GC
    // This is called from C# P/Invoke: TerminCore.ComponentBodyDecref
}
%}

// Export C API for C# to set callbacks and manage body
extern "C" {
    void tc_component_set_external_callbacks(const void* callbacks);
    void tc_component_body_incref(void* body);
    void tc_component_body_decref(void* body);
}

// Opaque type for tc_component
typedef struct tc_component tc_component;

// Typemap for void* as IntPtr (for set_external_body)
%typemap(cstype) void* body "System.IntPtr"
%typemap(csin) void* body "$csinput"
%typemap(imtype) void* body "System.IntPtr"

// Typemap for tc_component* as IntPtr
%typemap(cstype) tc_component* "System.IntPtr"
%typemap(csout) tc_component* { return $imcall; }
%typemap(imtype) tc_component* "System.IntPtr"
%typemap(out) tc_component* %{ $result = (void*)$1; %}

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
// Pass Registry API (C) - kept for low-level access
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

// ============================================================================
// C++ Render Classes
// ============================================================================

%{
#include "termin/render/render_pipeline.hpp"
#include "termin/render/render_engine.hpp"
#include "termin/render/mesh_renderer.hpp"
#include "termin/render/color_pass.hpp"
#include "termin/render/depth_pass.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/lighting/light.hpp"
%}

// Forward declarations
namespace termin {
    class GraphicsBackend;
    class FramebufferHandle;
    class Component;
    class CxxComponent;
    class Drawable;
    struct TcMesh;
    struct TcMaterial;
}

// Ignore problematic members
%ignore termin::RenderPipeline::pipeline_;
%ignore termin::RenderPipeline::specs_;
%ignore termin::RenderPipeline::fbo_pool_;
%ignore termin::RenderPipeline::shadow_arrays_;
%ignore termin::RenderPipeline::fbo_pool;
%ignore termin::RenderPipeline::shadow_arrays;
%ignore termin::RenderPipeline::collect_specs;
%ignore termin::RenderPipeline::operator=;

%ignore termin::RenderEngine::render_scene_pipeline_offscreen;

%ignore termin::MeshRenderer::mesh;
%ignore termin::MeshRenderer::material;
%ignore termin::MeshRenderer::_overridden_material;
%ignore termin::MeshRenderer::_pending_override_data;
%ignore termin::MeshRenderer::get_mesh;
%ignore termin::MeshRenderer::get_material_ref;
%ignore termin::MeshRenderer::get_material_ptr;
%ignore termin::MeshRenderer::get_base_material;
%ignore termin::MeshRenderer::get_overridden_material;
%ignore termin::MeshRenderer::get_phase_marks;
%ignore termin::MeshRenderer::phase_marks;
%ignore termin::MeshRenderer::draw_geometry;
%ignore termin::MeshRenderer::get_phases_for_mark;
%ignore termin::MeshRenderer::get_geometry_draws;
%ignore termin::MeshRenderer::get_override_data;
%ignore termin::MeshRenderer::set_override_data;
%ignore termin::MeshRenderer::try_create_override_material;

%ignore termin::CameraComponent::viewports_;
%ignore termin::CameraComponent::add_viewport;
%ignore termin::CameraComponent::remove_viewport;
%ignore termin::CameraComponent::has_viewport;
%ignore termin::CameraComponent::viewport_count;
%ignore termin::CameraComponent::viewport_at;
%ignore termin::CameraComponent::clear_viewports;
%ignore termin::CameraComponent::on_scene_inactive;
%ignore termin::CameraComponent::screen_point_to_ray;

%ignore termin::ColorPass::extra_textures;
%ignore termin::ColorPass::entity_names;
%ignore termin::ColorPass::extra_texture_uniforms;
%ignore termin::ColorPass::last_gpu_time_ms;
%ignore termin::ColorPass::clear_extra_textures;
%ignore termin::ColorPass::set_extra_texture_uniform;

%ignore termin::Light;

// Ignore problematic optional fields in ResourceSpec
%ignore termin::ResourceSpec::size;
%ignore termin::ResourceSpec::clear_color;
%ignore termin::ResourceSpec::clear_depth;
%ignore termin::ResourceSpec::format;

// Include ResourceSpec header
%{
#include "termin/render/resource_spec.hpp"
%}

namespace termin {

// ============================================================================
// ResourceSpec - FBO resource specification
// ============================================================================

struct ResourceSpec {
    std::string resource;
    std::string resource_type;
    int samples;
    std::string viewport_name;
    float scale;

    ResourceSpec();
};

// ============================================================================
// RenderPipeline - manages passes and FBO resources
// ============================================================================

class RenderPipeline {
public:
    RenderPipeline(const std::string& name = "default");
    ~RenderPipeline();

    // Name
    const std::string& name() const;
    void set_name(const std::string& name);

    // Pass management
    void add_pass(tc_pass* pass);
    void remove_pass(tc_pass* pass);
    void insert_pass_before(tc_pass* pass, tc_pass* before);
    tc_pass* get_pass(const std::string& name);
    tc_pass* get_pass_at(size_t index);
    size_t pass_count() const;

    // Specs management
    void add_spec(const ResourceSpec& spec);
    void clear_specs();
    size_t spec_count() const;
    const ResourceSpec* get_spec_at(size_t index) const;
};

// ============================================================================
// RenderEngine - executes render pipelines
// ============================================================================

class RenderEngine {
public:
    GraphicsBackend* graphics;

    RenderEngine();
    explicit RenderEngine(GraphicsBackend* graphics);

    // Render to screen (default FBO)
    void render_to_screen(
        RenderPipeline* pipeline,
        int width,
        int height,
        void* scene,
        CameraComponent* camera
    );
};

// ============================================================================
// CameraComponent - camera for rendering
// ============================================================================

class CameraComponent {
public:
    CameraProjection projection_type;
    double near_clip;
    double far_clip;
    double fov_y;
    double aspect;
    double ortho_size;

    CameraComponent();

    // Projection type
    std::string get_projection_type_str() const;
    void set_projection_type_str(const std::string& type);

    // FOV in degrees
    double get_fov_degrees() const;
    void set_fov_degrees(double deg);

    // Aspect ratio
    void set_aspect(double a);

    // Matrices
    Mat44 get_view_matrix() const;
    Mat44 get_projection_matrix() const;
    Mat44 compute_projection_matrix(double aspect_override) const;

    // Position
    Vec3 get_position() const;

    // Component pointer for C API interop
    tc_component* tc_component_ptr();

    // External body management (for C# prevent-GC mechanism)
    void set_external_body(void* body);
};

// ============================================================================
// MeshRenderer - renders a mesh with material
// ============================================================================

class MeshRenderer {
public:
    bool cast_shadow;

    MeshRenderer();
    virtual ~MeshRenderer();

    // Mesh by name
    void set_mesh_by_name(const std::string& name);

    // Material by name
    void set_material_by_name(const std::string& name);

    // Override material
    bool override_material() const;
    void set_override_material(bool value);

    // Component pointer for C API interop
    tc_component* tc_component_ptr();

    // External body management (for C# prevent-GC mechanism)
    void set_external_body(void* body);
};

// ============================================================================
// ColorPass - main color rendering pass
// ============================================================================

class ColorPass {
public:
    std::string input_res;
    std::string output_res;
    std::string shadow_res;
    std::string phase_mark;
    std::string sort_mode;
    std::string camera_name;
    bool clear_depth;
    bool wireframe;
    bool use_ubo;

    ColorPass(
        const std::string& input_res = "empty",
        const std::string& output_res = "color",
        const std::string& shadow_res = "shadow_maps",
        const std::string& phase_mark = "opaque",
        const std::string& pass_name = "Color",
        const std::string& sort_mode = "none",
        bool clear_depth = false,
        const std::string& camera_name = ""
    );
    virtual ~ColorPass();

    // Get tc_pass pointer for adding to pipeline
    tc_pass* tc_pass_ptr();
};

// ============================================================================
// DepthPass - depth-only rendering pass
// ============================================================================

class DepthPass {
public:
    std::string input_res;
    std::string output_res;

    DepthPass(
        const std::string& input_res = "empty",
        const std::string& output_res = "depth",
        const std::string& pass_name = "Depth"
    );
    virtual ~DepthPass();

    tc_pass* tc_pass_ptr();
};

} // namespace termin

// ============================================================================
// OpenGL Backend Initialization
// ============================================================================

%{
#include "tc_opengl.h"
%}

// OpenGL init functions
bool tc_opengl_init(void);
bool tc_opengl_is_initialized(void);
void tc_opengl_shutdown(void);
void* tc_opengl_get_graphics(void);

// Helper to cast void* to GraphicsBackend*
%inline %{
namespace termin {
    GraphicsBackend* get_opengl_graphics() {
        return static_cast<GraphicsBackend*>(tc_opengl_get_graphics());
    }
}
%}
