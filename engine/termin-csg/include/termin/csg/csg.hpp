#pragma once

#include <string>
#include <vector>

#include <tgfx/tgfx_mesh3.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

#include <termin/csg/termin_csg_api.hpp>
#include <termin/geom/vec2.hpp>
#include <termin/geom/vec3.hpp>

namespace termin::csg {

    using Point2 = Vec2;
    using Polygon2 = std::vector<Vec2>;

    class TERMIN_CSG_API Solid {
    private:
        struct Impl;
        Impl* impl_ = nullptr;

    public:
        Solid();
        Solid(const Solid&);
        Solid(Solid&&) noexcept;
        Solid& operator=(const Solid&);
        Solid& operator=(Solid&&) noexcept;
        ~Solid();

        bool is_empty() const;
        size_t vertex_count() const;
        size_t triangle_count() const;
        double volume() const;
        const char* status_string() const;

        Solid translated(const Vec3& offset) const;
        Solid scaled(const Vec3& factors) const;
        Solid rotated(const Vec3& euler_degrees) const;

    private:
        explicit Solid(Impl impl);

        friend TERMIN_CSG_API Solid make_box(const Vec3&, bool);
        friend TERMIN_CSG_API Solid make_sphere(double, int);
        friend TERMIN_CSG_API Solid make_cylinder(double, double, int, bool);
        friend TERMIN_CSG_API Solid make_cone(double, double, double, int, bool);
        friend TERMIN_CSG_API Solid unite(const Solid&, const Solid&);
        friend TERMIN_CSG_API Solid subtract(const Solid&, const Solid&);
        friend TERMIN_CSG_API Solid intersect(const Solid&, const Solid&);
        friend TERMIN_CSG_API Solid extrude(const Polygon2&, const std::vector<Polygon2>&, double);
        friend TERMIN_CSG_API Solid from_mesh3(const Mesh3&);
        friend TERMIN_CSG_API Mesh3 to_mesh3(const Solid&, const std::string&, const std::string&, bool);
    };

    TERMIN_CSG_API Solid make_box(const Vec3& size, bool centered = true);
    TERMIN_CSG_API Solid make_sphere(double radius, int circular_segments = 0);
    TERMIN_CSG_API Solid make_cylinder(double radius, double height, int circular_segments = 0, bool centered = true);
    TERMIN_CSG_API Solid
    make_cone(double radius_low, double radius_high, double height, int circular_segments = 0, bool centered = true);
    TERMIN_CSG_API Solid unite(const Solid& a, const Solid& b);
    TERMIN_CSG_API Solid subtract(const Solid& a, const Solid& b);
    TERMIN_CSG_API Solid intersect(const Solid& a, const Solid& b);
    TERMIN_CSG_API Solid from_mesh3(const Mesh3& mesh);

    // Builds a solid by extruding a 2D contour along +Z. The outer polygon and all
    // holes are interpreted in the local XY plane. Winding does not need to be
    // pre-normalized; Manifold/Clipper2 regularizes the cross-section internally.
    TERMIN_CSG_API Solid extrude(const Polygon2& outer, const std::vector<Polygon2>& holes, double height);

    TERMIN_CSG_API Mesh3 to_mesh3(const Solid& solid,
                                  const std::string& name = "",
                                  const std::string& uuid = "",
                                  bool flat_shading = false);

    TERMIN_CSG_API TcMesh to_tc_mesh(const Solid& solid,
                                     const std::string& name = "",
                                     const std::string& uuid = "",
                                     bool flat_shading = false);

} // namespace termin::csg
