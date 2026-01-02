#include "mesh_gpu.hpp"
#include "graphics_backend.hpp"

namespace termin {

void MeshGPU::draw(
    GraphicsBackend* graphics,
    const tc_mesh* mesh,
    int version,
    int64_t context_key
) {
    if (!mesh) return;

    // Get current cached mesh (may be null if handle is stale)
    tc_mesh* cached = tc_mesh_get(_cached_handle);

    // Update cached mesh reference
    if (cached != mesh) {
        if (cached) {
            tc_mesh_release(cached);
        }
        // Find handle for new mesh
        _cached_handle = tc_mesh_find(mesh->header.uuid);
        if (tc_mesh_handle_is_invalid(_cached_handle)) {
            return;
        }
        tc_mesh_add_ref(const_cast<tc_mesh*>(mesh));
    }

    // Check if we need to re-upload
    if (uploaded_version != version) {
        invalidate();
        uploaded_version = version;
    }

    // Upload to this context if needed
    auto it = handles.find(context_key);
    if (it == handles.end()) {
        auto handle = std::shared_ptr<GPUMeshHandle>(graphics->create_mesh(mesh).release());
        it = handles.emplace(context_key, std::move(handle)).first;
    }

    // Draw
    it->second->draw();
}

void MeshGPU::invalidate() {
    // Release all handles
    // Note: In multi-context scenario, we should switch contexts before deleting.
    // For now, we rely on the handle destructor to clean up.
    handles.clear();
}

} // namespace termin
