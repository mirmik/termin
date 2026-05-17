#include <termin/csg/csg.hpp>

#include <cstdint>
#include <utility>

#include <manifold/cross_section.h>
#include <manifold/manifold.h>
#include <manifold/polygon.h>

namespace termin::csg {
namespace {

using manifold::CrossSection;
using manifold::Manifold;
using manifold::Polygons;
using manifold::vec2;
using manifold::vec3;

Polygons make_polygons(const Polygon2& outer, const std::vector<Polygon2>& holes) {
    Polygons polygons;
    polygons.reserve(1 + holes.size());

    auto append = [&polygons](const Polygon2& polygon) {
        manifold::SimplePolygon simple;
        simple.reserve(polygon.size());
        for (const Point2& p : polygon) {
            simple.push_back(vec2(p.x, p.y));
        }
        polygons.push_back(std::move(simple));
    };

    append(outer);
    for (const Polygon2& hole : holes) {
        append(hole);
    }

    return polygons;
}

const char* status_to_string(Manifold::Error status) {
    switch (status) {
    case Manifold::Error::NoError:
        return "No Error";
    case Manifold::Error::NonFiniteVertex:
        return "Non Finite Vertex";
    case Manifold::Error::NotManifold:
        return "Not Manifold";
    case Manifold::Error::VertexOutOfBounds:
        return "Vertex Out Of Bounds";
    case Manifold::Error::PropertiesWrongLength:
        return "Properties Wrong Length";
    case Manifold::Error::MissingPositionProperties:
        return "Missing Position Properties";
    case Manifold::Error::MergeVectorsDifferentLengths:
        return "Merge Vectors Different Lengths";
    case Manifold::Error::MergeIndexOutOfBounds:
        return "Merge Index Out Of Bounds";
    case Manifold::Error::TransformWrongLength:
        return "Transform Wrong Length";
    case Manifold::Error::RunIndexWrongLength:
        return "Run Index Wrong Length";
    case Manifold::Error::FaceIDWrongLength:
        return "Face ID Wrong Length";
    case Manifold::Error::InvalidConstruction:
        return "Invalid Construction";
    case Manifold::Error::ResultTooLarge:
        return "Result Too Large";
    }
    return "Unknown Error";
}

Mesh3 make_flat_shaded(const Mesh3& source) {
    Mesh3 result;
    result.name = source.name;
    result.uuid = source.uuid;

    const size_t triangle_index_count = source.triangles.size();
    result.vertices.reserve(triangle_index_count);
    result.normals.reserve(triangle_index_count);
    result.triangles.reserve(triangle_index_count);

    for (size_t i = 0; i + 2 < triangle_index_count; i += 3) {
        const uint32_t i0 = source.triangles[i + 0];
        const uint32_t i1 = source.triangles[i + 1];
        const uint32_t i2 = source.triangles[i + 2];
        if (i0 >= source.vertices.size() ||
            i1 >= source.vertices.size() ||
            i2 >= source.vertices.size()) {
            continue;
        }

        const Vec3f& v0 = source.vertices[i0];
        const Vec3f& v1 = source.vertices[i1];
        const Vec3f& v2 = source.vertices[i2];
        const Vec3f normal = (v1 - v0).cross(v2 - v0).normalized();
        const uint32_t base = static_cast<uint32_t>(result.vertices.size());

        result.vertices.push_back(v0);
        result.vertices.push_back(v1);
        result.vertices.push_back(v2);
        result.normals.push_back(normal);
        result.normals.push_back(normal);
        result.normals.push_back(normal);
        result.triangles.push_back(base + 0);
        result.triangles.push_back(base + 1);
        result.triangles.push_back(base + 2);
    }

    return result;
}

} // namespace

struct Solid::Impl {
    Manifold manifold;

    Impl() = default;
    explicit Impl(Manifold value) : manifold(std::move(value)) {}
};

Solid::Solid() : impl_(new Impl()) {}

Solid::Solid(Impl impl) : impl_(new Impl(std::move(impl))) {}

Solid::Solid(const Solid& other) : impl_(new Impl(*other.impl_)) {}

Solid::Solid(Solid&& other) noexcept : impl_(other.impl_) {
    other.impl_ = nullptr;
}

Solid& Solid::operator=(const Solid& other) {
    if (this != &other) {
        *impl_ = *other.impl_;
    }
    return *this;
}

Solid& Solid::operator=(Solid&& other) noexcept {
    if (this != &other) {
        delete impl_;
        impl_ = other.impl_;
        other.impl_ = nullptr;
    }
    return *this;
}

Solid::~Solid() {
    delete impl_;
}

bool Solid::is_empty() const {
    return !impl_ || impl_->manifold.IsEmpty();
}

size_t Solid::vertex_count() const {
    return impl_ ? impl_->manifold.NumVert() : 0;
}

size_t Solid::triangle_count() const {
    return impl_ ? impl_->manifold.NumTri() : 0;
}

double Solid::volume() const {
    return impl_ ? impl_->manifold.Volume() : 0.0;
}

const char* Solid::status_string() const {
    if (!impl_) {
        return "No implementation";
    }
    return status_to_string(impl_->manifold.Status());
}

Solid Solid::translated(double x, double y, double z) const {
    if (!impl_) {
        return Solid();
    }
    return Solid(Impl(impl_->manifold.Translate(vec3(x, y, z))));
}

Solid Solid::scaled(double x, double y, double z) const {
    if (!impl_) {
        return Solid();
    }
    return Solid(Impl(impl_->manifold.Scale(vec3(x, y, z))));
}

Solid Solid::rotated(double x_degrees, double y_degrees, double z_degrees) const {
    if (!impl_) {
        return Solid();
    }
    return Solid(Impl(impl_->manifold.Rotate(x_degrees, y_degrees, z_degrees)));
}

Solid make_box(double x, double y, double z, bool centered) {
    return Solid(Solid::Impl(Manifold::Cube(vec3(x, y, z), centered)));
}

Solid make_sphere(double radius, int circular_segments) {
    return Solid(Solid::Impl(Manifold::Sphere(radius, circular_segments)));
}

Solid make_cylinder(double radius, double height, int circular_segments, bool centered) {
    return Solid(Solid::Impl(Manifold::Cylinder(height, radius, radius, circular_segments, centered)));
}

Solid make_cone(double radius_low, double radius_high, double height, int circular_segments, bool centered) {
    return Solid(Solid::Impl(Manifold::Cylinder(height, radius_low, radius_high, circular_segments, centered)));
}

Solid unite(const Solid& a, const Solid& b) {
    return Solid(Solid::Impl(a.impl_->manifold + b.impl_->manifold));
}

Solid subtract(const Solid& a, const Solid& b) {
    return Solid(Solid::Impl(a.impl_->manifold - b.impl_->manifold));
}

Solid intersect(const Solid& a, const Solid& b) {
    return Solid(Solid::Impl(a.impl_->manifold ^ b.impl_->manifold));
}

Solid extrude(const Polygon2& outer, const std::vector<Polygon2>& holes, double height) {
    CrossSection cross_section(make_polygons(outer, holes), CrossSection::FillRule::EvenOdd);
    return Solid(Solid::Impl(Manifold::Extrude(cross_section.ToPolygons(), height)));
}

Mesh3 to_mesh3(const Solid& solid,
               const std::string& name,
               const std::string& uuid,
               bool flat_shading) {
    Mesh3 mesh;
    mesh.name = name;
    mesh.uuid = uuid;

    if (!solid.impl_ || solid.impl_->manifold.IsEmpty()) {
        return mesh;
    }

    auto gl_mesh = solid.impl_->manifold.GetMeshGL();
    const size_t vertex_count = gl_mesh.NumVert();
    const size_t index_count = gl_mesh.triVerts.size();

    mesh.vertices.reserve(vertex_count);
    for (size_t i = 0; i < vertex_count; ++i) {
        const size_t base = i * gl_mesh.numProp;
        mesh.vertices.emplace_back(
            gl_mesh.vertProperties[base + 0],
            gl_mesh.vertProperties[base + 1],
            gl_mesh.vertProperties[base + 2]);
    }

    mesh.triangles.reserve(index_count);
    for (uint32_t index : gl_mesh.triVerts) {
        mesh.triangles.push_back(index);
    }

    if (flat_shading) {
        return make_flat_shaded(mesh);
    }

    mesh.compute_normals();
    return mesh;
}

TcMesh to_tc_mesh(const Solid& solid,
                  const std::string& name,
                  const std::string& uuid,
                  bool flat_shading) {
    return TcMesh::from_mesh3(to_mesh3(solid, name, uuid, flat_shading), name, uuid);
}

} // namespace termin::csg
