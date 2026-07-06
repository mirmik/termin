#include <termin/navmesh/navmesh_keeper_component.hpp>

#include <termin/navmesh/detour_navmesh_asset_utils.hpp>
#include <termin/navmesh/navmesh_query_space.hpp>
#include <termin/navmesh/tc_navmesh_handle.hpp>
#include <termin/entity/component_registry.hpp>
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
    register_component_type<NavMeshKeeperComponent>("NavMeshKeeperComponent", "Component");
    tc::InspectAccessorFieldRegistrar<NavMeshKeeperComponent, TcNavMesh>(
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

std::set<std::string> NavMeshKeeperComponent::get_phase_marks() const {
    if (navmesh_uuid.empty()) {
        return {};
    }
    return {NAVMESH_DEBUG_PHASE};
}

void NavMeshKeeperComponent::draw_geometry(const RenderContext& context, int geometry_id) {
    (void)context;
    (void)geometry_id;
    ensure_debug_mesh_loaded();
}

std::vector<GeometryDrawCall> NavMeshKeeperComponent::get_geometry_draws(
    const RenderContext& context,
    const std::string* phase_mark
) {
    std::vector<GeometryDrawCall> result;
    if ((context.render_category_mask & TC_RENDER_CATEGORY_NAVMESH) == 0) {
        return result;
    }
    if (phase_mark && *phase_mark != NAVMESH_DEBUG_PHASE) {
        return result;
    }
    if (!ensure_debug_mesh_loaded()) {
        return result;
    }

    TcMaterial mat = get_or_create_navmesh_debug_material(_navmesh_debug_material);
    if (!mat.is_valid()) {
        return result;
    }

    tc_material* material = mat.get();
    if (!material) {
        return result;
    }

    for (size_t i = 0; i < material->phase_count; ++i) {
        tc_material_phase* phase = &material->phases[i];
        if (phase_mark && phase->phase_mark != *phase_mark) {
            continue;
        }
        result.emplace_back(phase, 0);
    }
    return result;
}

tc_mesh* NavMeshKeeperComponent::get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const {
    (void)geometry_id;
    if (phase_mark != NAVMESH_DEBUG_PHASE) {
        return nullptr;
    }
    return ensure_debug_mesh_loaded() && _navmesh_debug_mesh.is_valid() ? _navmesh_debug_mesh.get() : nullptr;
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
