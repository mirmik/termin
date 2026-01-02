#pragma once

#include <unordered_map>
#include <memory>
#include <cstdint>
#include <cstdio>

#include "termin/render/handles.hpp"
#include "termin/render/render_context.hpp"

extern "C" {
#include "termin_core.h"
}

namespace termin {

/**
 * MeshGPU - GPU resource wrapper for mesh rendering.
 *
 * Manages GPU mesh buffers (VAO/VBO/EBO) with:
 * - Version tracking for automatic re-upload
 * - Multi-context support (multiple GL contexts)
 */
class MeshGPU {
public:
    // Uploaded version (-1 = never uploaded)
    int uploaded_version = -1;

    // GPU handles per context (shared_ptr for nanobind compatibility)
    std::unordered_map<int64_t, std::shared_ptr<GPUMeshHandle>> handles;

    // Cached mesh handle (safe - uses generation checking)
    tc_mesh_handle _cached_handle = tc_mesh_handle_invalid();

    MeshGPU() = default;

    ~MeshGPU() {
        if (tc_mesh* m = tc_mesh_get(_cached_handle)) {
            tc_mesh_release(m);
        }
        _cached_handle = tc_mesh_handle_invalid();
    }

    // Non-copyable (owns GPU resources)
    MeshGPU(const MeshGPU&) = delete;
    MeshGPU& operator=(const MeshGPU&) = delete;

    // Movable - transfer handle ownership
    MeshGPU(MeshGPU&& other) noexcept
        : uploaded_version(other.uploaded_version)
        , handles(std::move(other.handles))
        , _cached_handle(other._cached_handle)
    {
        other._cached_handle = tc_mesh_handle_invalid();
        other.uploaded_version = -1;
    }

    MeshGPU& operator=(MeshGPU&& other) noexcept {
        if (this != &other) {
            // Release our current mesh
            if (tc_mesh* m = tc_mesh_get(_cached_handle)) {
                tc_mesh_release(m);
            }
            // Move from other
            uploaded_version = other.uploaded_version;
            handles = std::move(other.handles);
            _cached_handle = other._cached_handle;
            // Null out other
            other._cached_handle = tc_mesh_handle_invalid();
            other.uploaded_version = -1;
        }
        return *this;
    }

    /**
     * Check if any GPU data is uploaded.
     */
    bool is_uploaded() const {
        return !handles.empty();
    }

    /**
     * Draw mesh, uploading/re-uploading if needed.
     *
     * @param graphics Graphics backend for GPU operations
     * @param mesh tc_mesh geometry data
     * @param version Current version of mesh data
     * @param context_key GL context key
     */
    void draw(
        GraphicsBackend* graphics,
        const tc_mesh* mesh,
        int version,
        int64_t context_key
    );

    /**
     * Draw tc_mesh using RenderContext (convenience overload).
     */
    void draw(const RenderContext& ctx, const tc_mesh* mesh, int version) {
        draw(ctx.graphics, mesh, version, ctx.context_key);
    }

    /**
     * Invalidate all GPU handles (e.g., when version changes).
     */
    void invalidate();

    /**
     * Explicitly delete all GPU resources.
     */
    void delete_resources() {
        invalidate();
        uploaded_version = -1;
        if (tc_mesh* m = tc_mesh_get(_cached_handle)) {
            tc_mesh_release(m);
        }
        _cached_handle = tc_mesh_handle_invalid();
    }
};

} // namespace termin
