#pragma once

// TcMesh - RAII wrapper with handle-based access to tc_mesh
// Uses tc_mesh_handle with generation checking for safety

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
// Stores handle (index + generation) instead of raw pointer
class TcMesh {
public:
    tc_mesh_handle handle = tc_mesh_handle_invalid();

    TcMesh() = default;

    explicit TcMesh(tc_mesh_handle h) : handle(h) {
        if (tc_mesh* m = tc_mesh_get(handle)) {
            tc_mesh_add_ref(m);
        }
    }

    // Construct from raw pointer (finds handle for it)
    explicit TcMesh(tc_mesh* m) {
        if (m) {
            handle = tc_mesh_find(m->uuid);
            tc_mesh_add_ref(m);
        }
    }

    TcMesh(const TcMesh& other) : handle(other.handle) {
        if (tc_mesh* m = tc_mesh_get(handle)) {
            tc_mesh_add_ref(m);
        }
    }

    TcMesh(TcMesh&& other) noexcept : handle(other.handle) {
        other.handle = tc_mesh_handle_invalid();
    }

    TcMesh& operator=(const TcMesh& other) {
        if (this != &other) {
            if (tc_mesh* m = tc_mesh_get(handle)) {
                tc_mesh_release(m);
            }
            handle = other.handle;
            if (tc_mesh* m = tc_mesh_get(handle)) {
                tc_mesh_add_ref(m);
            }
        }
        return *this;
    }

    TcMesh& operator=(TcMesh&& other) noexcept {
        if (this != &other) {
            if (tc_mesh* m = tc_mesh_get(handle)) {
                tc_mesh_release(m);
            }
            handle = other.handle;
            other.handle = tc_mesh_handle_invalid();
        }
        return *this;
    }

    ~TcMesh() {
        if (tc_mesh* m = tc_mesh_get(handle)) {
            tc_mesh_release(m);
        }
        handle = tc_mesh_handle_invalid();
    }

    // Get raw pointer (may return nullptr if handle is stale)
    tc_mesh* get() const { return tc_mesh_get(handle); }

    // For backwards compatibility
    tc_mesh* mesh_ptr() const { return get(); }

    // Query (safe - returns defaults if handle is stale)
    bool is_valid() const { return tc_mesh_is_valid(handle); }

    const char* uuid() const {
        tc_mesh* m = get();
        return m ? m->uuid : "";
    }

    const char* name() const {
        tc_mesh* m = get();
        return (m && m->name) ? m->name : "";
    }

    uint32_t version() const {
        tc_mesh* m = get();
        return m ? m->version : 0;
    }

    size_t vertex_count() const {
        tc_mesh* m = get();
        return m ? m->vertex_count : 0;
    }

    size_t index_count() const {
        tc_mesh* m = get();
        return m ? m->index_count : 0;
    }

    size_t triangle_count() const {
        tc_mesh* m = get();
        return m ? m->index_count / 3 : 0;
    }

    uint16_t stride() const {
        tc_mesh* m = get();
        return m ? m->layout.stride : 0;
    }

    const tc_vertex_layout* layout() const {
        tc_mesh* m = get();
        return m ? &m->layout : nullptr;
    }

    void bump_version() {
        if (tc_mesh* m = get()) {
            m->version++;
        }
    }

    // Create TcMesh from Mesh3 (CPU mesh)
    static TcMesh from_mesh3(const Mesh3& mesh,
                             const std::string& override_name = "",
                             const std::string& override_uuid = "",
                             const tc_vertex_layout* custom_layout = nullptr);

    // Create TcMesh from raw interleaved vertex data
    static TcMesh from_interleaved(
        const void* vertices, size_t vertex_count,
        const uint32_t* indices, size_t index_count,
        const tc_vertex_layout& layout,
        const std::string& name = "",
        const std::string& uuid_hint = "");

    // Get by UUID from registry
    static TcMesh from_uuid(const std::string& uuid) {
        tc_mesh_handle h = tc_mesh_find(uuid.c_str());
        if (tc_mesh_handle_is_invalid(h)) {
            return TcMesh();
        }
        return TcMesh(h);
    }

    // Get or create by UUID
    static TcMesh get_or_create(const std::string& uuid) {
        tc_mesh_handle h = tc_mesh_get_or_create(uuid.c_str());
        if (tc_mesh_handle_is_invalid(h)) {
            return TcMesh();
        }
        return TcMesh(h);
    }
};

} // namespace termin
