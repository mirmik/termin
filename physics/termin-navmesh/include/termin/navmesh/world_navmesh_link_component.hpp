#pragma once
#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>

namespace termin {
    // Explicit walkable seam between independent, potentially moving bake frames.
    // Endpoints are in each referenced surface entity's local coordinates.
    class TERMIN_NAVMESH_COMPONENTS_API WorldNavMeshLinkComponent : public CxxComponent {
    public:
        Entity start_surface;
        Entity end_surface;
        tc_vec3 start_local{0, 0, 0};
        tc_vec3 end_local{0, 0, 0};
        double snap_radius = 0.5;
        bool bidirectional = true;
        WorldNavMeshLinkComponent()
            : CxxComponent("WorldNavMeshLinkComponent") {}
        ~WorldNavMeshLinkComponent() override;
        static void register_type();
        void on_added() override;
        void on_removed() override;
    };
} // namespace termin
