#pragma once

#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>

namespace termin {

struct TERMIN_NAVMESH_COMPONENTS_API NavMeshBakeContext {
    Entity builder_entity;
    Mat44 world_to_bake;
    std::string agent_type_name;
    float agent_radius = 0.5f;
    float agent_height = 2.0f;
    float agent_max_climb = 0.4f;
    int default_area_id = 0;
};

struct TERMIN_NAVMESH_COMPONENTS_API NavMeshGeometryBatch {
    std::vector<float> verts;
    std::vector<int> tris;
    std::vector<unsigned char> triangle_area_ids;
    int area_id = 0;
    Entity source;
    std::string debug_name;
};

struct TERMIN_NAVMESH_COMPONENTS_API NavMeshOffMeshLinkRecord {
    float start[3] = {0.0f, 0.0f, 0.0f};
    float end[3] = {0.0f, 0.0f, 0.0f};
    float radius = 0.0f;
    unsigned char direction = 0;
    unsigned char area_id = 0;
    unsigned short flags = 1;
    unsigned int user_id = 0;
    Entity source;
    std::string debug_name;
};

struct TERMIN_NAVMESH_COMPONENTS_API NavMeshBakeInput {
    std::vector<NavMeshGeometryBatch> geometry;
    std::vector<NavMeshOffMeshLinkRecord> off_mesh_links;
    int visited_registered_component_count = 0;

    bool has_geometry() const;
    int triangle_count() const;
    int vertex_count() const;
    int off_mesh_link_count() const;

    void add_geometry_batch(NavMeshGeometryBatch batch);
    void add_off_mesh_link(NavMeshOffMeshLinkRecord link);
};

using NavMeshBakeVisitor = std::function<void(
    Entity,
    CxxComponent*,
    const NavMeshBakeContext&,
    NavMeshBakeInput&)>;

class TERMIN_NAVMESH_COMPONENTS_API NavMeshBakeVisitorRegistry {
public:
    static NavMeshBakeVisitorRegistry& instance();

    void register_geometry_visitor(const std::string& component_type, NavMeshBakeVisitor visitor);
    void register_link_visitor(const std::string& component_type, NavMeshBakeVisitor visitor);
    void ensure_builtin_visitors_registered();

    const NavMeshBakeVisitor* geometry_visitor(const std::string& component_type) const;
    const NavMeshBakeVisitor* link_visitor(const std::string& component_type) const;
    int visit_component(Entity entity,
                        CxxComponent* component,
                        const char* component_type,
                        const NavMeshBakeContext& context,
                        NavMeshBakeInput& input) const;

private:
    std::unordered_map<std::string, NavMeshBakeVisitor> _geometry_visitors;
    std::unordered_map<std::string, NavMeshBakeVisitor> _link_visitors;
    bool _builtin_visitors_registered = false;
};

TERMIN_NAVMESH_COMPONENTS_API NavMeshBakeInput collect_navmesh_bake_input(
    const NavMeshBakeContext& context,
    const std::vector<Entity>& entities);

TERMIN_NAVMESH_COMPONENTS_API unsigned int stable_navmesh_source_user_id(
    Entity source,
    const std::string& local_id);

TERMIN_NAVMESH_COMPONENTS_API unsigned char navmesh_detour_area_to_recast_area(int area_id);
TERMIN_NAVMESH_COMPONENTS_API unsigned char navmesh_recast_area_to_detour_area(
    unsigned char recast_area,
    int fallback_area_id);

} // namespace termin
