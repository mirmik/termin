#pragma once

#include <string>
#include <vector>

#include <tgfx/tgfx_mesh3.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

namespace termin::csg {

struct Point2 {
    double x = 0.0;
    double y = 0.0;
};

using Polygon2 = std::vector<Point2>;

class Solid {
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

    Solid translated(double x, double y, double z) const;
    Solid scaled(double x, double y, double z) const;
    Solid rotated(double x_degrees, double y_degrees, double z_degrees) const;

private:
    struct Impl;
    explicit Solid(Impl impl);

    Impl* impl_ = nullptr;

    friend Solid make_box(double, double, double, bool);
    friend Solid make_sphere(double, int);
    friend Solid make_cylinder(double, double, int, bool);
    friend Solid make_cone(double, double, double, int, bool);
    friend Solid unite(const Solid&, const Solid&);
    friend Solid subtract(const Solid&, const Solid&);
    friend Solid intersect(const Solid&, const Solid&);
    friend Solid extrude(const Polygon2&, const std::vector<Polygon2>&, double);
    friend Mesh3 to_mesh3(const Solid&, const std::string&, const std::string&);
};

Solid make_box(double x, double y, double z, bool centered = true);
Solid make_sphere(double radius, int circular_segments = 0);
Solid make_cylinder(double radius, double height, int circular_segments = 0, bool centered = true);
Solid make_cone(double radius_low, double radius_high, double height, int circular_segments = 0, bool centered = true);
Solid unite(const Solid& a, const Solid& b);
Solid subtract(const Solid& a, const Solid& b);
Solid intersect(const Solid& a, const Solid& b);

// Builds a solid by extruding a 2D contour along +Z. The outer polygon and all
// holes are interpreted in the local XY plane. Winding does not need to be
// pre-normalized; Manifold/Clipper2 regularizes the cross-section internally.
Solid extrude(const Polygon2& outer, const std::vector<Polygon2>& holes, double height);

Mesh3 to_mesh3(const Solid& solid,
               const std::string& name = "",
               const std::string& uuid = "");

TcMesh to_tc_mesh(const Solid& solid,
                  const std::string& name = "",
                  const std::string& uuid = "");

} // namespace termin::csg
