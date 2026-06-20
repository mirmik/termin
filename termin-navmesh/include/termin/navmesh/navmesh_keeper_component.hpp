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

public:
    std::string navmesh_uuid;

    NavMeshKeeperComponent();

    std::set<std::string> get_phase_marks() const override;
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;
    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override;
    tc_mesh* get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const override;

private:
    mutable std::string _loaded_navmesh_uuid;
    mutable std::string _loaded_asset_path;
    mutable TcMesh _navmesh_debug_mesh;
    mutable TcMaterial _navmesh_debug_material;
    mutable bool _load_failed = false;

    bool ensure_debug_mesh_loaded() const;
    void invalidate_debug_mesh() const;
};

} // namespace termin
