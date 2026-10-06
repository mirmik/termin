#pragma once

#include <set>
#include <string>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/render_lifecycle.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

namespace termin {

    class RecastNavMeshBuilderComponent;

    class TERMIN_NAVMESH_COMPONENTS_API NavMeshKeeperComponent : public CxxComponent, public Drawable, public RenderLifecycle {
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

        tc_phase_mask get_phase_mask() const override;
        // prepare_render refreshes cached geometry before lightweight enumeration.
        void prepare_render(const RenderPrepareContext& context) override;
        bool collect_materials(const tc_render_item_collect_context& context, tc_material_sink& sink) override;
        bool collect_render_items(const tc_render_item_collect_context& context, tc_render_item_sink& sink) override;
        Mat44f get_model_matrix(const Entity& entity) const override;

    private:
        template <typename Visit>
        bool visit_material_phases(const tc_render_item_collect_context& context, Visit&& visit);
        bool ensure_debug_mesh_loaded() const;
        void invalidate_debug_mesh() const;
    };

} // namespace termin
