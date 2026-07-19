#include <termin/navmesh/navmesh_keeper_component.hpp>

#include <termin/navmesh/detour_navmesh_asset_utils.hpp>
#include <termin/navmesh/navmesh_query_space.hpp>
#include <termin/navmesh/tc_navmesh_handle.hpp>
#include <termin/entity/component_registry.hpp>
#include <cstring>
#include <utility>
#include <tcbase/tc_log.hpp>

extern "C" {
#include <render/tc_render_category_flags.h>
}

namespace termin {

namespace {

Mat44f to_mat44f(const Mat44& value) {
    Mat44f result;
    for (int i = 0; i < 16; ++i) {
        result.data[i] = static_cast<float>(value.data[i]);
    }
    return result;
}

} // namespace

NavMeshKeeperComponent::NavMeshKeeperComponent()
    : CxxComponent("NavMeshKeeperComponent")
{
    install_drawable_vtable(&_c);
}

void NavMeshKeeperComponent::register_type() {
    auto descriptor = ComponentTypeDescriptorBuilder::native<NavMeshKeeperComponent>(
        "NavMeshKeeperComponent", "termin-navmesh", "Component");
    descriptor.category("Navigation");
    descriptor.inspect().add_with_accessors<NavMeshKeeperComponent, TcNavMesh>(
        "NavMeshKeeperComponent",
        "navmesh",
        "NavMesh",
        "navmesh_handle",
        [](NavMeshKeeperComponent* self) {
            return TcNavMesh::from_uuid(self->navmesh_uuid);
        },
        [](NavMeshKeeperComponent* self, TcNavMesh value) {
            const char* uuid = value.uuid();
            self->navmesh_uuid = uuid ? uuid : "";
        }
    );
    (void)descriptor.commit();
}

void NavMeshKeeperComponent::invalidate_debug_mesh() const {
    _loaded_navmesh_uuid.clear();
    _loaded_asset_path.clear();
    _navmesh_debug_mesh = TcMesh();
    _load_failed = false;
}

bool NavMeshKeeperComponent::ensure_debug_mesh_loaded() const {
    if (navmesh_uuid.empty()) {
        invalidate_debug_mesh();
        return false;
    }
    if (_loaded_navmesh_uuid == navmesh_uuid && _navmesh_debug_mesh.is_valid()) {
        return true;
    }
    if (_loaded_navmesh_uuid == navmesh_uuid && _load_failed) {
        return false;
    }

    invalidate_debug_mesh();
    _loaded_navmesh_uuid = navmesh_uuid;

    TcNavMesh navmesh = TcNavMesh::from_uuid(navmesh_uuid);
    if (!navmesh.is_valid()) {
        tc_log_warn("[NavMeshKeeperComponent] navmesh not found for uuid=%s", navmesh_uuid.c_str());
        _load_failed = true;
        return false;
    }
    _loaded_asset_path = navmesh.name();
    _navmesh_debug_mesh = build_detour_debug_mesh(navmesh);

    if (!_navmesh_debug_mesh.is_valid()) {
        _load_failed = true;
        return false;
    }

    return true;
}

tc_phase_mask NavMeshKeeperComponent::get_phase_mask() const {
    if (navmesh_uuid.empty()) {
        return TC_PHASE_NONE;
    }
    return TC_PHASE_EDITOR_DEBUG;
}

bool NavMeshKeeperComponent::collect_render_items(
    const tc_render_item_collect_context& context,
    tc_render_item_sink& sink)
{
    if (!sink.emit) {
        tc_log_error("[NavMeshKeeperComponent] cannot emit render items: sink callback is null");
        return false;
    }
    if (context.phase != TC_PHASE_NONE && context.phase != TC_PHASE_EDITOR_DEBUG) {
        return true;
    }
    if ((context.render_category_mask & TC_RENDER_CATEGORY_NAVMESH) == 0) {
        return true;
    }
    if (!ensure_debug_mesh_loaded() || !_navmesh_debug_mesh.is_valid()) {
        return true;
    }

    TcMaterial mat = get_or_create_navmesh_debug_material(_navmesh_debug_material);
    tc_material* material = mat.get();
    tc_mesh* mesh = _navmesh_debug_mesh.get();
    if (!material || !mesh) {
        return true;
    }

    tc_material_phase* phases[TC_MATERIAL_MAX_PHASES];
    const size_t count = tc_material_get_phases_for_phase(
        material,
        TC_PHASE_EDITOR_DEBUG,
        phases,
        TC_MATERIAL_MAX_PHASES);
    Mat44f model = get_model_matrix(entity());
    for (size_t i = 0; i < count; ++i) {
        tc_material_phase* phase = phases[i];
        tc_render_item item{};
        item.kind = TC_RENDER_ITEM_KIND_MESH;
        item.flags = TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX | TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE;
        item.component = tc_component_ptr();
        item.geometry_id = 0;
        item.material_phase = phase;
        item.material = mat.handle;
        item.material_phase_index = static_cast<size_t>(phase - material->phases);
        std::memcpy(item.model_matrix, model.data, sizeof(float) * 16);
        item.payload.mesh.mesh = mesh;
        item.payload.mesh.mesh_handle = _navmesh_debug_mesh.handle;
        item.payload.mesh.submesh_index = 0;
        if (!sink.emit(&item, sink.user_data)) {
            return false;
        }
    }
    return true;
}

Mat44f NavMeshKeeperComponent::get_model_matrix(const Entity& entity) const {
    if (!entity.valid()) {
        tc_log_error("[NavMeshKeeperComponent] cannot compute debug model matrix: entity is invalid");
        return Mat44f::identity();
    }

    const Pose3 bake_frame = navmesh_bake_frame_from_pose(entity.transform().global_pose());
    return to_mat44f(bake_frame.as_mat44());
}

} // namespace termin
