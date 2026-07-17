#include <termin/render/skinned_mesh_renderer.hpp>
#include <termin/render/skeleton_controller.hpp>
#include <termin/entity/entity.hpp>
#include <cstdint>

namespace termin {

void SkinnedMeshRenderer::register_type() {
    register_component_type<SkinnedMeshRenderer>("SkinnedMeshRenderer", "MeshRenderer");
    ComponentRegistry::instance().set_category("SkinnedMeshRenderer", "Rendering");
    register_component_requirement("SkinnedMeshRenderer", "MeshComponent");
}

SkinnedMeshRenderer::SkinnedMeshRenderer()
    : MeshRenderer("SkinnedMeshRenderer")
{
}

SkinnedMeshRenderer::~SkinnedMeshRenderer() = default;

void SkinnedMeshRenderer::set_skeleton_controller(SkeletonController* controller) {
    _skeleton_controller.reset(controller);
}

void SkinnedMeshRenderer::resolve_skeleton_controller() {
    if (_skeleton_controller.valid() || !entity().valid()) {
        return;
    }

    Entity owner = entity();

    auto try_resolve_on_entity = [this](Entity candidate) -> bool {
        if (!candidate.valid()) {
            return false;
        }
        Component* controller = candidate.get_component_by_type("SkeletonController");
        if (controller != nullptr) {
            _skeleton_controller.reset(dynamic_cast<SkeletonController*>(controller));
            return _skeleton_controller.valid();
        }
        return false;
    };

    if (try_resolve_on_entity(owner)) {
        return;
    }

    // Scene copy/deserialization does not preserve transient CmpRef values.
    // Imported GLB meshes may be nested below Armature or intermediate nodes,
    // while the SkeletonController lives on the model root.
    Entity ancestor = owner.parent();
    while (ancestor.valid()) {
        if (try_resolve_on_entity(ancestor)) {
            return;
        }
        ancestor = ancestor.parent();
    }
}

SkeletonInstance* SkinnedMeshRenderer::skeleton_instance() {
    resolve_skeleton_controller();
    SkeletonController* ctrl = _skeleton_controller.get();
    if (!ctrl) {
        return nullptr;
    }
    return ctrl->skeleton_instance();
}

void SkinnedMeshRenderer::update_bone_matrices() {
    SkeletonInstance* si = skeleton_instance();
    if (si == nullptr) {
        _bone_count = 0;
        _bone_matrices_flat.clear();
        return;
    }

    // Skinning shader applies this renderer's u_model after bone matrices.
    // Compute bones in renderer-local space to avoid mixing Armature/root space
    // with per-mesh draw space.
    if (entity().valid()) {
        si->update(entity());
    } else {
        si->update();
    }

    // Get bone count
    _bone_count = si->bone_count();
    if (_bone_count == 0) {
        _bone_matrices_flat.clear();
        return;
    }

    // Resize buffer
    _bone_matrices_flat.resize(_bone_count * 16);

    // Copy matrices (column-major for OpenGL)
    for (int i = 0; i < _bone_count; ++i) {
        const Mat44& m = si->get_bone_matrix(i);
        // Mat44 is column-major, copy directly
        for (int j = 0; j < 16; ++j) {
            _bone_matrices_flat[i * 16 + j] = static_cast<float>(m.data[j]);
        }
    }
}

void SkinnedMeshRenderer::populate_mesh_render_item(tc_render_item& item) {
    update_bone_matrices();
    if (_bone_count <= 0 || _bone_matrices_flat.empty()) {
        return;
    }

    item.flags |= TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES;
    item.payload.mesh.skinning_matrices = _bone_matrices_flat.data();
    item.payload.mesh.skinning_matrix_count = static_cast<uint32_t>(_bone_count);
}

void SkinnedMeshRenderer::start() {
    Component::start();
    resolve_skeleton_controller();
}

} // namespace termin
