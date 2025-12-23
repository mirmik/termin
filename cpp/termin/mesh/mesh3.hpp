#pragma once

#include <vector>
#include <string>
#include <cmath>
#include <algorithm>

namespace termin {

/**
 * Triangle mesh with positions, normals, and UVs.
 */
class Mesh3 {
public:
    // Vertex data (Nx3)
    std::vector<float> vertices;  // Flattened: [x0,y0,z0, x1,y1,z1, ...]

    // Triangle indices (Mx3)
    std::vector<uint32_t> indices;  // Flattened: [i0,j0,k0, i1,j1,k1, ...]

    // Optional UV coordinates (Nx2)
    std::vector<float> uvs;  // Flattened: [u0,v0, u1,v1, ...]

    // Optional vertex normals (Nx3)
    std::vector<float> vertex_normals;  // Flattened: [nx0,ny0,nz0, ...]

    // Optional face normals (Mx3)
    std::vector<float> face_normals;  // Flattened

    // Optional source path
    std::string source_path;

    Mesh3() = default;

    Mesh3(std::vector<float> verts, std::vector<uint32_t> tris)
        : vertices(std::move(verts)), indices(std::move(tris)) {}

    // Number of vertices
    size_t get_vertex_count() const {
        return vertices.size() / 3;
    }

    // Number of triangles
    size_t get_face_count() const {
        return indices.size() / 3;
    }

    // Check if has UVs
    bool has_uvs() const {
        return !uvs.empty();
    }

    // Check if has vertex normals
    bool has_vertex_normals() const {
        return !vertex_normals.empty();
    }

    // Get vertex at index
    void get_vertex(size_t idx, float& x, float& y, float& z) const {
        size_t base = idx * 3;
        x = vertices[base];
        y = vertices[base + 1];
        z = vertices[base + 2];
    }

    // Set vertex at index
    void set_vertex(size_t idx, float x, float y, float z) {
        size_t base = idx * 3;
        vertices[base] = x;
        vertices[base + 1] = y;
        vertices[base + 2] = z;
    }

    // Translate all vertices
    void translate(float dx, float dy, float dz) {
        for (size_t i = 0; i < vertices.size(); i += 3) {
            vertices[i] += dx;
            vertices[i + 1] += dy;
            vertices[i + 2] += dz;
        }
    }

    // Scale all vertices
    void scale(float factor) {
        for (auto& v : vertices) {
            v *= factor;
        }
    }

    // Compute face normals
    void compute_face_normals() {
        size_t num_faces = get_face_count();
        face_normals.resize(num_faces * 3);

        for (size_t f = 0; f < num_faces; ++f) {
            uint32_t i0 = indices[f * 3];
            uint32_t i1 = indices[f * 3 + 1];
            uint32_t i2 = indices[f * 3 + 2];

            float v0x = vertices[i0 * 3], v0y = vertices[i0 * 3 + 1], v0z = vertices[i0 * 3 + 2];
            float v1x = vertices[i1 * 3], v1y = vertices[i1 * 3 + 1], v1z = vertices[i1 * 3 + 2];
            float v2x = vertices[i2 * 3], v2y = vertices[i2 * 3 + 1], v2z = vertices[i2 * 3 + 2];

            // Edge vectors
            float e1x = v1x - v0x, e1y = v1y - v0y, e1z = v1z - v0z;
            float e2x = v2x - v0x, e2y = v2y - v0y, e2z = v2z - v0z;

            // Cross product
            float nx = e1y * e2z - e1z * e2y;
            float ny = e1z * e2x - e1x * e2z;
            float nz = e1x * e2y - e1y * e2x;

            // Normalize
            float len = std::sqrt(nx * nx + ny * ny + nz * nz);
            if (len > 1e-8f) {
                nx /= len;
                ny /= len;
                nz /= len;
            }

            face_normals[f * 3] = nx;
            face_normals[f * 3 + 1] = ny;
            face_normals[f * 3 + 2] = nz;
        }
    }

    // Compute area-weighted vertex normals
    void compute_vertex_normals() {
        size_t num_verts = get_vertex_count();
        size_t num_faces = get_face_count();

        // Accumulate normals
        std::vector<double> accum(num_verts * 3, 0.0);

        for (size_t f = 0; f < num_faces; ++f) {
            uint32_t i0 = indices[f * 3];
            uint32_t i1 = indices[f * 3 + 1];
            uint32_t i2 = indices[f * 3 + 2];

            float v0x = vertices[i0 * 3], v0y = vertices[i0 * 3 + 1], v0z = vertices[i0 * 3 + 2];
            float v1x = vertices[i1 * 3], v1y = vertices[i1 * 3 + 1], v1z = vertices[i1 * 3 + 2];
            float v2x = vertices[i2 * 3], v2y = vertices[i2 * 3 + 1], v2z = vertices[i2 * 3 + 2];

            // Edge vectors
            float e1x = v1x - v0x, e1y = v1y - v0y, e1z = v1z - v0z;
            float e2x = v2x - v0x, e2y = v2y - v0y, e2z = v2z - v0z;

            // Cross product (area-weighted normal)
            double nx = e1y * e2z - e1z * e2y;
            double ny = e1z * e2x - e1x * e2z;
            double nz = e1x * e2y - e1y * e2x;

            // Accumulate to each vertex of the face
            accum[i0 * 3] += nx;
            accum[i0 * 3 + 1] += ny;
            accum[i0 * 3 + 2] += nz;

            accum[i1 * 3] += nx;
            accum[i1 * 3 + 1] += ny;
            accum[i1 * 3 + 2] += nz;

            accum[i2 * 3] += nx;
            accum[i2 * 3 + 1] += ny;
            accum[i2 * 3 + 2] += nz;
        }

        // Normalize and store
        vertex_normals.resize(num_verts * 3);
        for (size_t v = 0; v < num_verts; ++v) {
            double nx = accum[v * 3];
            double ny = accum[v * 3 + 1];
            double nz = accum[v * 3 + 2];
            double len = std::sqrt(nx * nx + ny * ny + nz * nz);
            if (len < 1e-8) len = 1.0;
            vertex_normals[v * 3] = static_cast<float>(nx / len);
            vertex_normals[v * 3 + 1] = static_cast<float>(ny / len);
            vertex_normals[v * 3 + 2] = static_cast<float>(nz / len);
        }
    }

    // Build interleaved buffer: pos(3) + normal(3) + uv(2) = 8 floats per vertex
    std::vector<float> build_interleaved_buffer() const {
        size_t num_verts = get_vertex_count();
        std::vector<float> buffer(num_verts * 8);

        for (size_t v = 0; v < num_verts; ++v) {
            size_t src = v * 3;
            size_t dst = v * 8;

            // Position
            buffer[dst] = vertices[src];
            buffer[dst + 1] = vertices[src + 1];
            buffer[dst + 2] = vertices[src + 2];

            // Normal
            if (!vertex_normals.empty()) {
                buffer[dst + 3] = vertex_normals[src];
                buffer[dst + 4] = vertex_normals[src + 1];
                buffer[dst + 5] = vertex_normals[src + 2];
            } else {
                buffer[dst + 3] = 0.0f;
                buffer[dst + 4] = 0.0f;
                buffer[dst + 5] = 0.0f;
            }

            // UV
            if (!uvs.empty()) {
                buffer[dst + 6] = uvs[v * 2];
                buffer[dst + 7] = uvs[v * 2 + 1];
            } else {
                buffer[dst + 6] = 0.0f;
                buffer[dst + 7] = 0.0f;
            }
        }

        return buffer;
    }

    // Create a deep copy
    Mesh3 copy() const {
        Mesh3 result;
        result.vertices = vertices;
        result.indices = indices;
        result.uvs = uvs;
        result.vertex_normals = vertex_normals;
        result.face_normals = face_normals;
        result.source_path = source_path;
        return result;
    }
};

} // namespace termin
