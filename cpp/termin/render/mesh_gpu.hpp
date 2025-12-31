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

    // Cached mesh pointer (with ref count)
    tc_mesh* _cached_mesh = nullptr;

    MeshGPU() = default;

    ~MeshGPU() {
        if (_cached_mesh) {
            tc_mesh_release(_cached_mesh);
            _cached_mesh = nullptr;
        }
    }

    // Non-copyable (owns GPU resources)
    MeshGPU(const MeshGPU&) = delete;
    MeshGPU& operator=(const MeshGPU&) = delete;

    // Movable
    MeshGPU(MeshGPU&&) = default;
    MeshGPU& operator=(MeshGPU&&) = default;

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
        if (_cached_mesh) {
            tc_mesh_release(_cached_mesh);
            _cached_mesh = nullptr;
        }
    }
};

} // namespace termin
