#pragma once

#include <memory>
#include <cstdint>

#include <termin/geom/mat44.hpp>
#include "tgfx/types.hpp"
#include "tgfx2/handles.hpp"

namespace tgfx {
class RenderContext2;
class IRenderDevice;
}

namespace termin {

// Solid primitive renderer using pre-built GPU meshes.
// Rendered through tgfx::RenderContext2 end-to-end.
// All geometry is created once at initialization via tgfx2 buffers,
// drawing sets model matrices and colors per-primitive via ctx2's
// transitional plain-uniform setters.
class SolidPrimitiveRenderer {
public:
    // Mesh parameters
    static constexpr int TORUS_MAJOR_SEGMENTS = 32;
    static constexpr int TORUS_MINOR_SEGMENTS = 8;
    static constexpr float TORUS_MINOR_RATIO = 0.03f;
    static constexpr int CYLINDER_SEGMENTS = 16;
    static constexpr int CONE_SEGMENTS = 16;

    // tgfx2 buffer resources per primitive.
    struct MeshRes {
        tgfx::BufferHandle vbo;
        tgfx::BufferHandle ibo;
        uint32_t index_count = 0;
    };
    MeshRes _torus;
    MeshRes _cylinder;
    MeshRes _cone;
    MeshRes _quad;

    bool _initialized = false;
    tgfx::ShaderHandle _vs;
    tgfx::ShaderHandle _fs;
    tgfx::IRenderDevice* _device = nullptr;
    tgfx::RenderContext2* _ctx2 = nullptr;
    // View-projection cached per begin() — premultiplied with per-draw
    // model so push_constants only carries mvp + color (80 bytes, fits
    // the 128-byte Vulkan guarantee).
    Mat44f _vp = Mat44f::identity();

public:
    SolidPrimitiveRenderer() = default;
    ~SolidPrimitiveRenderer();

    // Non-copyable
    SolidPrimitiveRenderer(const SolidPrimitiveRenderer&) = delete;
    SolidPrimitiveRenderer& operator=(const SolidPrimitiveRenderer&) = delete;

    // Movable
    SolidPrimitiveRenderer(SolidPrimitiveRenderer&& other) noexcept;
    SolidPrimitiveRenderer& operator=(SolidPrimitiveRenderer&& other) noexcept;

    // Begin solid primitive rendering. Sets up shader and state via
    // ctx2. A render pass must already be open on ctx2 before this is
    // called — begin() does NOT call ctx2->begin_pass (the caller
    // already owns the pass boundary).
    void begin(
        tgfx::RenderContext2* ctx2,
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
    void _ensure_initialized(tgfx::IRenderDevice* device);
    void _push_and_draw(const Mat44f& model, const Color4& color, const MeshRes& mesh);
};

} // namespace termin
