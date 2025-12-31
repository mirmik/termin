#pragma once

// TcMesh - RAII wrapper for tc_mesh* (GPU-ready mesh with layouts)

extern "C" {
#include "termin_core.h"
}

#include "cpu_mesh3.hpp"
#include <string>
#include <cstring>

namespace termin {

// TcMesh - GPU-ready mesh wrapper
// Manages tc_mesh* with reference counting
class TcMesh {
public:
    tc_mesh* mesh = nullptr;

    TcMesh() = default;

    explicit TcMesh(tc_mesh* m) : mesh(m) {
        if (mesh) tc_mesh_add_ref(mesh);
    }

    TcMesh(const TcMesh& other) : mesh(other.mesh) {
        if (mesh) tc_mesh_add_ref(mesh);
    }

    TcMesh(TcMesh&& other) noexcept : mesh(other.mesh) {
        other.mesh = nullptr;
    }

    TcMesh& operator=(const TcMesh& other) {
        if (this != &other) {
            if (mesh) tc_mesh_release(mesh);
            mesh = other.mesh;
            if (mesh) tc_mesh_add_ref(mesh);
        }
        return *this;
    }

    TcMesh& operator=(TcMesh&& other) noexcept {
        if (this != &other) {
            if (mesh) tc_mesh_release(mesh);
            mesh = other.mesh;
            other.mesh = nullptr;
        }
        return *this;
    }

    ~TcMesh() {
        if (mesh) {
            tc_mesh_release(mesh);
            mesh = nullptr;
        }
    }

    // Query
    bool is_valid() const { return mesh != nullptr; }
    const char* uuid() const { return mesh ? mesh->uuid : ""; }
    const char* name() const { return mesh && mesh->name ? mesh->name : ""; }
    uint32_t version() const { return mesh ? mesh->version : 0; }
    size_t vertex_count() const { return mesh ? mesh->vertex_count : 0; }
    size_t index_count() const { return mesh ? mesh->index_count : 0; }
    size_t triangle_count() const { return mesh ? mesh->index_count / 3 : 0; }
    uint16_t stride() const { return mesh ? mesh->layout.stride : 0; }
    const tc_vertex_layout& layout() const { return mesh->layout; }

    void bump_version() {
        if (mesh) mesh->version++;
    }

    // Create TcMesh from CpuMesh3
    // Uses CpuMesh3's uuid for caching if available
    static TcMesh from_cpu_mesh3(const CpuMesh3& cpu_mesh,
                                  const std::string& name = "",
                                  const tc_vertex_layout* custom_layout = nullptr) {
        if (cpu_mesh.vertices.empty()) {
            return TcMesh();
        }

        // Use uuid from cpu_mesh if provided, otherwise compute from data
        std::string uuid_str = cpu_mesh.uuid;

        // Check if already in registry
        if (!uuid_str.empty()) {
            tc_mesh* existing = tc_mesh_get(uuid_str.c_str());
            if (existing) {
                return TcMesh(existing);
            }
        }

        // Default layout: position(3) + normal(3) + uv(2) = 32 bytes
        tc_vertex_layout layout = custom_layout ? *custom_layout : tc_vertex_layout_pos_normal_uv();

        // Build interleaved vertex buffer
        size_t num_verts = cpu_mesh.vertices.size();
        size_t stride = layout.stride;
        std::vector<uint8_t> buffer(num_verts * stride, 0);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&layout, "uv");

        for (size_t i = 0; i < num_verts; i++) {
            uint8_t* dst = buffer.data() + i * stride;

            // Position
            if (pos_attr) {
                float* p = reinterpret_cast<float*>(dst + pos_attr->offset);
                p[0] = cpu_mesh.vertices[i].x;
                p[1] = cpu_mesh.vertices[i].y;
                p[2] = cpu_mesh.vertices[i].z;
            }

            // Normal
            if (norm_attr && i < cpu_mesh.normals.size()) {
                float* n = reinterpret_cast<float*>(dst + norm_attr->offset);
                n[0] = cpu_mesh.normals[i].x;
                n[1] = cpu_mesh.normals[i].y;
                n[2] = cpu_mesh.normals[i].z;
            }

            // UV
            if (uv_attr && i < cpu_mesh.uvs.size()) {
                float* u = reinterpret_cast<float*>(dst + uv_attr->offset);
                u[0] = cpu_mesh.uvs[i].x;
                u[1] = cpu_mesh.uvs[i].y;
            }
        }

        // Compute UUID from data if not provided
        if (uuid_str.empty()) {
            char computed_uuid[40];
            tc_mesh_compute_uuid(buffer.data(), buffer.size(),
                                cpu_mesh.triangles.data(), cpu_mesh.triangles.size(),
                                computed_uuid);
            uuid_str = computed_uuid;
        }

        // Get or create mesh in registry
        tc_mesh* m = tc_mesh_get_or_create(uuid_str.c_str());
        if (!m) {
            return TcMesh();
        }

        // Set data if mesh is new (vertex_count == 0)
        if (m->vertex_count == 0) {
            std::string mesh_name = name.empty() ? cpu_mesh.name : name;
            tc_mesh_set_data(m,
                            buffer.data(), num_verts, &layout,
                            cpu_mesh.triangles.data(), cpu_mesh.triangles.size(),
                            mesh_name.empty() ? nullptr : mesh_name.c_str());
        }

        return TcMesh(m);
    }

    // Get by UUID from registry
    static TcMesh from_uuid(const std::string& uuid) {
        tc_mesh* m = tc_mesh_get(uuid.c_str());
        return TcMesh(m);
    }

    // Get or create by UUID
    static TcMesh get_or_create(const std::string& uuid) {
        tc_mesh* m = tc_mesh_get_or_create(uuid.c_str());
        return TcMesh(m);
    }
};

} // namespace termin
