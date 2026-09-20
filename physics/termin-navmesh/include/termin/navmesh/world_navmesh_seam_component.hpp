#pragma once
#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>
namespace termin {
    // Declares a traversable strip between two explicitly paired surface boundaries.
    class TERMIN_NAVMESH_COMPONENTS_API WorldNavMeshSeamComponent : public CxxComponent {
    public:
        Entity start_surface, end_surface;
        tc_vec3 start_a{0, 0, 0}, start_b{0, 1, 0};
        tc_vec3 end_a{0, 0, 0}, end_b{0, 1, 0};
        double max_extension = 0.75;
        bool bidirectional = true;
        WorldNavMeshSeamComponent()
            : CxxComponent("WorldNavMeshSeamComponent") {}
        ~WorldNavMeshSeamComponent() override;
        static void register_type();
        void on_added() override;
        void on_removed() override;
    };
} // namespace termin
