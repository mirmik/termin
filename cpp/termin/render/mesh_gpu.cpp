#include "mesh_gpu.hpp"
#include "graphics_backend.hpp"
#include "termin/mesh/mesh3.hpp"

namespace termin {

void MeshGPU::draw(
    GraphicsBackend* graphics,
    const Mesh3& mesh,
    int version,
    int64_t context_key
) {
    // Check if we need to re-upload
    if (uploaded_version != version) {
        invalidate();
        uploaded_version = version;
    }

    // Upload to this context if needed
    auto it = handles.find(context_key);
    if (it == handles.end()) {
        // create_mesh returns unique_ptr, convert to shared_ptr
        auto handle = std::shared_ptr<GPUMeshHandle>(graphics->create_mesh(mesh).release());
        it = handles.emplace(context_key, std::move(handle)).first;
    }

    // Draw
    it->second->draw();
}

void MeshGPU::draw(
    GraphicsBackend* graphics,
    const tc_mesh* mesh,
    int version,
    int64_t context_key
) {
    if (!mesh) return;

    // Update cached mesh reference
    if (_cached_mesh != mesh) {
        if (_cached_mesh) tc_mesh_release(_cached_mesh);
        _cached_mesh = const_cast<tc_mesh*>(mesh);
        tc_mesh_add_ref(_cached_mesh);
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
