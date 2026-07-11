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

struct TERMIN_NAVMESH_COMPONENTS_API NavMeshLinearPathSegmentRecord {
    float start[3] = {0.0f, 0.0f, 0.0f};
    float end[3] = {0.0f, 0.0f, 0.0f};
    unsigned char area_id = 0;
    unsigned short flags = 1;
    unsigned int user_id = 0;
    Entity source;
    std::string debug_name;
};

struct TERMIN_NAVMESH_COMPONENTS_API NavMeshLinearPathLinkRecord {
    int from_segment = -1;
    int to_segment = -1;
    unsigned short from_t = 0;
    unsigned short to_t = 0;
    unsigned char flags = 1;
    Entity source;
    std::string debug_name;
};

struct TERMIN_NAVMESH_COMPONENTS_API NavMeshBakeInput {
    std::vector<NavMeshGeometryBatch> geometry;
    std::vector<NavMeshOffMeshLinkRecord> off_mesh_links;
    std::vector<NavMeshLinearPathSegmentRecord> linear_segments;
    std::vector<NavMeshLinearPathLinkRecord> linear_links;
    int visited_registered_component_count = 0;

    bool has_geometry() const;
    int triangle_count() const;
    int vertex_count() const;
    int off_mesh_link_count() const;
    int linear_segment_count() const;
    int linear_link_count() const;

    void add_geometry_batch(NavMeshGeometryBatch batch);
    void add_off_mesh_link(NavMeshOffMeshLinkRecord link);
    int add_linear_segment(NavMeshLinearPathSegmentRecord segment);
    void add_linear_link(NavMeshLinearPathLinkRecord link);
};

using NavMeshBakeVisitor = std::function<void(
    Entity,
    CxxComponent*,
    const NavMeshBakeContext&,
    NavMeshBakeInput&)>;

class TERMIN_NAVMESH_COMPONENTS_API NavMeshBakeVisitorRegistry {
private:
    struct VisitorRecord {
        NavMeshBakeVisitor visitor;
        std::string owner;
    };
    using VisitorMap = std::unordered_map<std::string, VisitorRecord>;
    VisitorMap _geometry_visitors;
    VisitorMap _link_visitors;
    VisitorMap _linear_visitors;
    std::string _current_registration_owner;
    bool _builtin_visitors_registered = false;

public:
    static NavMeshBakeVisitorRegistry& instance();

    bool register_geometry_visitor(const std::string& component_type, NavMeshBakeVisitor visitor);
    bool register_link_visitor(const std::string& component_type, NavMeshBakeVisitor visitor);
    bool register_linear_visitor(const std::string& component_type, NavMeshBakeVisitor visitor);
    bool unregister_geometry_visitor(const std::string& component_type);
    bool unregister_link_visitor(const std::string& component_type);
    bool unregister_linear_visitor(const std::string& component_type);
    size_t unregister_owner(const std::string& owner);
    void set_registration_owner(const std::string& owner);
    std::string registration_owner() const;
    std::string geometry_visitor_owner(const std::string& component_type) const;
    std::string link_visitor_owner(const std::string& component_type) const;
    std::string linear_visitor_owner(const std::string& component_type) const;
    void ensure_builtin_visitors_registered();

    const NavMeshBakeVisitor* geometry_visitor(const std::string& component_type) const;
    const NavMeshBakeVisitor* link_visitor(const std::string& component_type) const;
    const NavMeshBakeVisitor* linear_visitor(const std::string& component_type) const;
    int visit_component(Entity entity,
                        CxxComponent* component,
                        const char* component_type,
                        const NavMeshBakeContext& context,
                        NavMeshBakeInput& input) const;

    bool register_visitor(VisitorMap& visitors,
                          const char* visitor_kind,
                          const std::string& component_type,
                          NavMeshBakeVisitor visitor,
                          const std::string& owner);
    static bool unregister_visitor(VisitorMap& visitors, const std::string& component_type);
    static std::string visitor_owner(const VisitorMap& visitors, const std::string& component_type);

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
