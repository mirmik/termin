#pragma once

// TcMesh - RAII wrapper for tc_mesh* (GPU-ready mesh with layouts)
// Registers mesh data in tc_mesh C registry.

extern "C" {
#include "termin_core.h"
}

#include <string>
#include <cstring>
#include <vector>

namespace termin {

// Forward declaration
class Mesh3;

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

    // Create TcMesh from Mesh3 (CPU mesh)
    // Uses override_uuid if provided, otherwise Mesh3's uuid for caching
    static TcMesh from_mesh3(const Mesh3& mesh,
                             const std::string& override_name = "",
                             const std::string& override_uuid = "",
                             const tc_vertex_layout* custom_layout = nullptr);

    // Create TcMesh from raw interleaved vertex data
    // Used for GLB meshes where data is already in GPU format
    static TcMesh from_interleaved(
        const void* vertices, size_t vertex_count,
        const uint32_t* indices, size_t index_count,
        const tc_vertex_layout& layout,
        const std::string& name = "",
        const std::string& uuid_hint = "");

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
