#pragma once

#include <memory>
#include <cstdint>

#include "termin/geom/mat44.hpp"
#include "tgfx/types.hpp"
#include "tgfx/handles.hpp"
#include "termin/render/tc_shader_handle.hpp"

namespace termin {

class GraphicsBackend;

// Solid primitive renderer using pre-built GPU meshes.
// All geometry is created once at initialization.
// Drawing is done by setting model matrices and colors per-primitive.
class SolidPrimitiveRenderer {
public:
    // Mesh parameters
    static constexpr int TORUS_MAJOR_SEGMENTS = 32;
    static constexpr int TORUS_MINOR_SEGMENTS = 8;
    static constexpr float TORUS_MINOR_RATIO = 0.03f;
    static constexpr int CYLINDER_SEGMENTS = 16;
    static constexpr int CONE_SEGMENTS = 16;

    // GPU mesh handles for each primitive type
    GPUMeshHandlePtr _torus_mesh;
    GPUMeshHandlePtr _cylinder_mesh;
    GPUMeshHandlePtr _cone_mesh;
    GPUMeshHandlePtr _quad_mesh;

    bool _initialized = false;
    TcShader _shader;
    GraphicsBackend* _graphics = nullptr;

public:
    SolidPrimitiveRenderer() = default;
    ~SolidPrimitiveRenderer() = default;

    // Non-copyable
    SolidPrimitiveRenderer(const SolidPrimitiveRenderer&) = delete;
    SolidPrimitiveRenderer& operator=(const SolidPrimitiveRenderer&) = delete;

    // Movable
    SolidPrimitiveRenderer(SolidPrimitiveRenderer&& other) noexcept;
    SolidPrimitiveRenderer& operator=(SolidPrimitiveRenderer&& other) noexcept;

    // Begin solid primitive rendering. Sets up shader and state.
    void begin(
        GraphicsBackend* graphics,
        const Mat44f& view,
        const Mat44f& proj,
        bool depth_test = true,
        bool blend = false
    );

    // End solid primitive rendering.
    void end();

    // Draw a torus using model matrix.
    // Unit torus has major_radius=1, minor_radius=TORUS_MINOR_RATIO.
    // Axis is Z. Model matrix should include position and scale.
    void draw_torus(const Mat44f& model, const Color4& color);

    // Draw a cylinder using model matrix.
    // Unit cylinder has radius=1, height=1 (Z from 0 to 1).
    void draw_cylinder(const Mat44f& model, const Color4& color);

    // Draw a cone using model matrix.
    // Unit cone has base_radius=1, height=1 (base at Z=0, tip at Z=1).
    void draw_cone(const Mat44f& model, const Color4& color);

    // Draw a quad using model matrix.
    // Unit quad is from (0,0,0) to (1,1,0) in XY plane.
    void draw_quad(const Mat44f& model, const Color4& color);

    // Draw a solid arrow (cylinder shaft + cone head).
    void draw_arrow(
        const Vec3f& origin,
        const Vec3f& direction,
        float length,
        const Color4& color,
        float shaft_radius = 0.02f,
        float head_radius = 0.06f,
        float head_length_ratio = 0.2f
    );

private:
    void _ensure_initialized(GraphicsBackend* graphics);
};

} // namespace termin
