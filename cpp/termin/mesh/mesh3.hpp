#pragma once

// Pure CPU triangle mesh for geometric operations.
// No GPU layouts, no tc_mesh registry - just vertices and triangles.
// uuid field is a hint for TcMesh creation (TcMesh registers in tc_mesh with this uuid).

#include <vector>
#include <string>
#include <cstdint>

#include "termin/geom/vec3.hpp"

namespace termin {

// Simple Vec2f for UV coordinates (no geom/vec2.hpp exists)
struct Vec2f {
    float x = 0, y = 0;
    Vec2f() = default;
    Vec2f(float x_, float y_) : x(x_), y(y_) {}
};

// Pure CPU triangle mesh
class Mesh3 {
public:
    std::vector<Vec3f> vertices;
    std::vector<uint32_t> triangles;  // flat: [i0, i1, i2, i0, i1, i2, ...]
    std::vector<Vec3f> normals;       // per-vertex normals (optional)
    std::vector<Vec2f> uvs;           // per-vertex UVs (optional)
    std::string name;
    std::string uuid;  // optional UUID for caching when converting to TcMesh

    Mesh3() = default;

    Mesh3(std::vector<Vec3f> verts, std::vector<uint32_t> tris,
          std::string mesh_name = "", std::string mesh_uuid = "")
        : vertices(std::move(verts))
        , triangles(std::move(tris))
        , name(std::move(mesh_name))
        , uuid(std::move(mesh_uuid))
    {}

    // Query
    size_t vertex_count() const { return vertices.size(); }
    size_t triangle_count() const { return triangles.size() / 3; }
    bool has_normals() const { return normals.size() == vertices.size(); }
    bool has_uvs() const { return uvs.size() == vertices.size(); }
    bool is_valid() const { return !vertices.empty() && !triangles.empty(); }

    // Compute per-vertex normals from triangles
    void compute_normals() {
        if (vertices.empty() || triangles.empty()) return;

        normals.resize(vertices.size());
        for (auto& n : normals) n = {0, 0, 0};

        size_t num_tris = triangle_count();
        for (size_t t = 0; t < num_tris; t++) {
            uint32_t i0 = triangles[t * 3];
            uint32_t i1 = triangles[t * 3 + 1];
            uint32_t i2 = triangles[t * 3 + 2];

            if (i0 >= vertices.size() || i1 >= vertices.size() || i2 >= vertices.size()) {
                continue;
            }

            Vec3f e1 = vertices[i1] - vertices[i0];
            Vec3f e2 = vertices[i2] - vertices[i0];
            Vec3f face_normal = e1.cross(e2);

            normals[i0] += face_normal;
            normals[i1] += face_normal;
            normals[i2] += face_normal;
        }

        for (auto& n : normals) {
            n = n.normalized();
        }
    }

    // Transformations
    void translate(float dx, float dy, float dz) {
        for (auto& v : vertices) {
            v.x += dx;
            v.y += dy;
            v.z += dz;
        }
    }

    void scale(float factor) {
        for (auto& v : vertices) {
            v.x *= factor;
            v.y *= factor;
            v.z *= factor;
        }
    }

    void scale(float sx, float sy, float sz) {
        for (auto& v : vertices) {
            v.x *= sx;
            v.y *= sy;
            v.z *= sz;
        }
    }

    // Copy
    Mesh3 copy(const std::string& new_name = "") const {
        Mesh3 result;
        result.vertices = vertices;
        result.triangles = triangles;
        result.normals = normals;
        result.uvs = uvs;
        result.name = new_name.empty() ? (name + "_copy") : new_name;
        return result;
    }
};

} // namespace termin
