#pragma once

#include <set>
#include <string>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/render/drawable.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>

namespace termin {

class RecastNavMeshBuilderComponent;

class TERMIN_NAVMESH_COMPONENTS_API NavMeshKeeperComponent : public CxxComponent, public Drawable {
    friend class RecastNavMeshBuilderComponent;

private:
    mutable std::string _loaded_navmesh_uuid;
    mutable std::string _loaded_asset_path;
    mutable TcMesh _navmesh_debug_mesh;
    mutable TcMaterial _navmesh_debug_material;
    mutable bool _load_failed = false;

public:
    std::string navmesh_uuid;

    NavMeshKeeperComponent();

    static void register_type();

    std::set<std::string> get_phase_marks() const override;
    bool collect_render_items(
        const tc_render_item_collect_context& context,
        tc_render_item_sink& sink) override;
    Mat44f get_model_matrix(const Entity& entity) const override;

private:
    bool ensure_debug_mesh_loaded() const;
    void invalidate_debug_mesh() const;
};

} // namespace termin
