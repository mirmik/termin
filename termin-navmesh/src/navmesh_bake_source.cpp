#include <termin/navmesh/navmesh_bake_source.hpp>

#include <termin/navmesh/off_mesh_link_component.hpp>
#include <components/mesh_component.hpp>
#include <DetourNavMesh.h>
#include <Recast.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <string>
#include <utility>
#include <tcbase/tc_log.hpp>

namespace termin {

namespace {

Mat44 mat44_from_mat44f(const Mat44f& value) {
    Mat44 result;
    for (int i = 0; i < 16; ++i) {
        result.data[i] = static_cast<double>(value.data[i]);
    }
    return result;
}

Vec3 termin_bake_to_recast(const Vec3& point) {
    return Vec3{point.x, point.z, point.y};
}

std::string entity_debug_name(Entity entity) {
    if (!entity.valid()) {
        return "(invalid)";
    }
    const char* name = entity.name();
    return name && name[0] ? std::string(name) : std::string("(unnamed)");
}

bool extract_mesh_positions(
    const TcMesh& mesh,
    const Mat44& transform,
    int area_id,
    Entity source,
    const std::string& debug_name,
    NavMeshBakeInput& input);

bool extract_mesh_component(
    Entity entity,
    MeshComponent& mesh_component,
    const NavMeshBakeContext& context,
    NavMeshBakeInput& input)
{
    if (!mesh_component.mesh.is_valid()) {
        return false;
    }

    double world_data[16];
    entity.get_world_matrix(world_data);
    Mat44 world;
    std::memcpy(world.ptr(), world_data, sizeof(world_data));
    Mat44 local_to_bake = context.world_to_bake * world;
    Mat44 mesh_to_bake =
        local_to_bake * mat44_from_mat44f(mesh_component.get_mesh_offset_matrix());

    tc_log_info("[NavMesh] Processing mesh source entity: %s",
                entity_debug_name(entity).c_str());

    return extract_mesh_positions(
        mesh_component.mesh,
        mesh_to_bake,
        context.default_area_id,
        entity,
        entity_debug_name(entity),
        input);
}

bool extract_mesh_positions(
    const TcMesh& mesh,
    const Mat44& transform,
    int area_id,
    Entity source,
    const std::string& debug_name,
    NavMeshBakeInput& input)
{
    tc_mesh* m = mesh.get();
    if (!m || !m->vertices || m->vertex_count == 0) {
        tc_log_error("[NavMesh] source '%s' has no mesh vertices", debug_name.c_str());
        return false;
    }
    if (!m->indices || m->index_count == 0) {
        tc_log_error("[NavMesh] source '%s' has no mesh indices", debug_name.c_str());
        return false;
    }

    const tc_vertex_attrib* pos = tc_vertex_layout_find(&m->layout, "position");
    if (!pos || pos->size != 3) {
        tc_log_error("[NavMesh] source '%s' mesh has no vec3 position attribute", debug_name.c_str());
        return false;
    }

    NavMeshGeometryBatch batch;
    batch.area_id = area_id;
    batch.source = source;
    batch.debug_name = debug_name;

    const size_t vertex_count = m->vertex_count;
    const size_t stride = m->layout.stride;
    const uint8_t* src = static_cast<const uint8_t*>(m->vertices);
    batch.verts.resize(vertex_count * 3);
    for (size_t i = 0; i < vertex_count; ++i) {
        const float* p = reinterpret_cast<const float*>(src + i * stride + pos->offset);
        Vec3 local_pos{p[0], p[1], p[2]};
        Vec3 bake_pos = transform.transform_point(local_pos);
        Vec3 recast_pos = termin_bake_to_recast(bake_pos);
        batch.verts[i * 3] = static_cast<float>(recast_pos.x);
        batch.verts[i * 3 + 1] = static_cast<float>(recast_pos.y);
        batch.verts[i * 3 + 2] = static_cast<float>(recast_pos.z);
    }

    const size_t triangle_count = m->index_count / 3;
    batch.tris.resize(triangle_count * 3);
    for (size_t i = 0; i < triangle_count * 3; ++i) {
        batch.tris[i] = static_cast<int>(m->indices[i]);
    }
    batch.triangle_area_ids.assign(triangle_count, static_cast<unsigned char>(
        std::clamp(area_id, 0, 63)));

    input.add_geometry_batch(std::move(batch));
    return true;
}

void collect_mesh_component(
    Entity entity,
    CxxComponent* component,
    const NavMeshBakeContext& context,
    NavMeshBakeInput& input)
{
    MeshComponent* mesh = dynamic_cast<MeshComponent*>(component);
    if (!mesh) {
        return;
    }
    input.visited_registered_component_count++;
    extract_mesh_component(entity, *mesh, context, input);
}

void collect_off_mesh_link_component(
    Entity entity,
    CxxComponent* component,
    const NavMeshBakeContext& context,
    NavMeshBakeInput& input)
{
    OffMeshLinkComponent* link = dynamic_cast<OffMeshLinkComponent*>(component);
    if (!link) {
        return;
    }
    input.visited_registered_component_count++;
    if (!link->enabled || link->agent_type != context.agent_type_name) {
        return;
    }

    Vec3 start_bake = context.world_to_bake.transform_point(link->start_world());
    Vec3 end_bake = context.world_to_bake.transform_point(link->end_world());
    Vec3 start_recast = termin_bake_to_recast(start_bake);
    Vec3 end_recast = termin_bake_to_recast(end_bake);

    NavMeshOffMeshLinkRecord record;
    record.start[0] = static_cast<float>(start_recast.x);
    record.start[1] = static_cast<float>(start_recast.y);
    record.start[2] = static_cast<float>(start_recast.z);
    record.end[0] = static_cast<float>(end_recast.x);
    record.end[1] = static_cast<float>(end_recast.y);
    record.end[2] = static_cast<float>(end_recast.z);
    record.radius = static_cast<float>(link->radius);
    record.direction = link->bidirectional ? DT_OFFMESH_CON_BIDIR : 0;
    const int area_id = std::clamp(link->area_id, 0, 63);
    if (area_id != link->area_id) {
        tc_log_warn("[NavMesh] OffMeshLinkComponent area_id=%d is outside Detour range, using %d",
                    link->area_id, area_id);
    }
    record.area_id = static_cast<unsigned char>(area_id);
    record.flags = 1;
    record.user_id = link->stable_user_id != 0
        ? link->stable_user_id
        : stable_navmesh_source_user_id(entity, "OffMeshLinkComponent");
    record.source = entity;
    record.debug_name = entity_debug_name(entity);

    input.add_off_mesh_link(record);
}

bool is_finite_point(const float point[3]) {
    return std::isfinite(point[0]) && std::isfinite(point[1]) && std::isfinite(point[2]);
}

} // namespace

bool NavMeshBakeInput::has_geometry() const {
    return !geometry.empty();
}

int NavMeshBakeInput::triangle_count() const {
    size_t count = 0;
    for (const NavMeshGeometryBatch& batch : geometry) {
        count += batch.tris.size() / 3;
    }
    return static_cast<int>(count);
}

int NavMeshBakeInput::vertex_count() const {
    size_t count = 0;
    for (const NavMeshGeometryBatch& batch : geometry) {
        count += batch.verts.size() / 3;
    }
    return static_cast<int>(count);
}

int NavMeshBakeInput::off_mesh_link_count() const {
    return static_cast<int>(off_mesh_links.size());
}

int NavMeshBakeInput::linear_segment_count() const {
    return static_cast<int>(linear_segments.size());
}

int NavMeshBakeInput::linear_link_count() const {
    return static_cast<int>(linear_links.size());
}

void NavMeshBakeInput::add_geometry_batch(NavMeshGeometryBatch batch) {
    if (batch.tris.size() % 3 != 0 || batch.verts.size() % 3 != 0) {
        tc_log_error("[NavMesh] rejecting invalid geometry batch '%s': verts=%zu tris=%zu",
                     batch.debug_name.c_str(),
                     batch.verts.size(),
                     batch.tris.size());
        return;
    }
    const size_t triangle_count = batch.tris.size() / 3;
    if (batch.triangle_area_ids.empty()) {
        batch.triangle_area_ids.assign(
            triangle_count,
            static_cast<unsigned char>(std::clamp(batch.area_id, 0, 63)));
    }
    if (batch.triangle_area_ids.size() != triangle_count) {
        tc_log_error("[NavMesh] rejecting geometry batch '%s': triangle area count %zu does not match triangle count %zu",
                     batch.debug_name.c_str(),
                     batch.triangle_area_ids.size(),
                     triangle_count);
        return;
    }
    geometry.push_back(std::move(batch));
}

void NavMeshBakeInput::add_off_mesh_link(NavMeshOffMeshLinkRecord link) {
    if (link.user_id == 0) {
        tc_log_error("[NavMesh] rejecting off-mesh link '%s': stable user id is zero",
                     link.debug_name.c_str());
        return;
    }
    off_mesh_links.push_back(std::move(link));
}

int NavMeshBakeInput::add_linear_segment(NavMeshLinearPathSegmentRecord segment) {
    if (!is_finite_point(segment.start) || !is_finite_point(segment.end)) {
        tc_log_error("[NavMesh] rejecting linear segment '%s': endpoint contains non-finite coordinates",
                     segment.debug_name.c_str());
        return -1;
    }
    if (segment.user_id == 0) {
        tc_log_error("[NavMesh] rejecting linear segment '%s': stable user id is zero",
                     segment.debug_name.c_str());
        return -1;
    }
    linear_segments.push_back(std::move(segment));
    return static_cast<int>(linear_segments.size()) - 1;
}

void NavMeshBakeInput::add_linear_link(NavMeshLinearPathLinkRecord link) {
    const int segment_count = linear_segment_count();
    if (link.from_segment < 0 || link.to_segment < 0 ||
        link.from_segment >= segment_count || link.to_segment >= segment_count) {
        tc_log_error("[NavMesh] rejecting linear link '%s': invalid segment indices from=%d to=%d segments=%d",
                     link.debug_name.c_str(),
                     link.from_segment,
                     link.to_segment,
                     segment_count);
        return;
    }
    linear_links.push_back(std::move(link));
}

NavMeshBakeVisitorRegistry& NavMeshBakeVisitorRegistry::instance() {
    static NavMeshBakeVisitorRegistry registry;
    return registry;
}

bool NavMeshBakeVisitorRegistry::register_geometry_visitor(
    const std::string& component_type,
    NavMeshBakeVisitor visitor)
{
    return register_visitor(
        _geometry_visitors,
        "geometry",
        component_type,
        std::move(visitor),
        _current_registration_owner);
}

bool NavMeshBakeVisitorRegistry::register_link_visitor(
    const std::string& component_type,
    NavMeshBakeVisitor visitor)
{
    return register_visitor(
        _link_visitors,
        "off-mesh link",
        component_type,
        std::move(visitor),
        _current_registration_owner);
}

bool NavMeshBakeVisitorRegistry::register_linear_visitor(
    const std::string& component_type,
    NavMeshBakeVisitor visitor)
{
    return register_visitor(
        _linear_visitors,
        "linear path",
        component_type,
        std::move(visitor),
        _current_registration_owner);
}

bool NavMeshBakeVisitorRegistry::unregister_geometry_visitor(
    const std::string& component_type)
{
    return unregister_visitor(_geometry_visitors, component_type);
}

bool NavMeshBakeVisitorRegistry::unregister_link_visitor(
    const std::string& component_type)
{
    return unregister_visitor(_link_visitors, component_type);
}

bool NavMeshBakeVisitorRegistry::unregister_linear_visitor(
    const std::string& component_type)
{
    return unregister_visitor(_linear_visitors, component_type);
}

size_t NavMeshBakeVisitorRegistry::unregister_owner(const std::string& owner) {
    if (owner.empty()) {
        return 0;
    }

    size_t removed = 0;
    auto remove_owned = [&owner, &removed](VisitorMap& visitors) {
        for (auto it = visitors.begin(); it != visitors.end();) {
            if (it->second.owner == owner) {
                it = visitors.erase(it);
                ++removed;
            } else {
                ++it;
            }
        }
    };
    remove_owned(_geometry_visitors);
    remove_owned(_link_visitors);
    remove_owned(_linear_visitors);
    return removed;
}

void NavMeshBakeVisitorRegistry::set_registration_owner(const std::string& owner) {
    _current_registration_owner = owner;
}

std::string NavMeshBakeVisitorRegistry::registration_owner() const {
    return _current_registration_owner;
}

std::string NavMeshBakeVisitorRegistry::geometry_visitor_owner(
    const std::string& component_type) const
{
    return visitor_owner(_geometry_visitors, component_type);
}

std::string NavMeshBakeVisitorRegistry::link_visitor_owner(
    const std::string& component_type) const
{
    return visitor_owner(_link_visitors, component_type);
}

std::string NavMeshBakeVisitorRegistry::linear_visitor_owner(
    const std::string& component_type) const
{
    return visitor_owner(_linear_visitors, component_type);
}

void NavMeshBakeVisitorRegistry::ensure_builtin_visitors_registered() {
    if (_builtin_visitors_registered) {
        return;
    }
    register_visitor(_geometry_visitors, "geometry", "MeshComponent", collect_mesh_component, "");
    register_visitor(_link_visitors, "off-mesh link", "OffMeshLinkComponent", collect_off_mesh_link_component, "");
    _builtin_visitors_registered = true;
}

const NavMeshBakeVisitor* NavMeshBakeVisitorRegistry::geometry_visitor(
    const std::string& component_type) const
{
    auto it = _geometry_visitors.find(component_type);
    return it == _geometry_visitors.end() ? nullptr : &it->second.visitor;
}

const NavMeshBakeVisitor* NavMeshBakeVisitorRegistry::link_visitor(
    const std::string& component_type) const
{
    auto it = _link_visitors.find(component_type);
    return it == _link_visitors.end() ? nullptr : &it->second.visitor;
}

const NavMeshBakeVisitor* NavMeshBakeVisitorRegistry::linear_visitor(
    const std::string& component_type) const
{
    auto it = _linear_visitors.find(component_type);
    return it == _linear_visitors.end() ? nullptr : &it->second.visitor;
}

bool NavMeshBakeVisitorRegistry::register_visitor(
    VisitorMap& visitors,
    const char* visitor_kind,
    const std::string& component_type,
    NavMeshBakeVisitor visitor,
    const std::string& owner)
{
    if (component_type.empty()) {
        tc_log_error("[NavMesh] cannot register %s bake visitor for empty component type",
                     visitor_kind ? visitor_kind : "unknown");
        return false;
    }
    if (!visitor) {
        tc_log_error("[NavMesh] cannot register empty %s bake visitor for component type '%s'",
                     visitor_kind ? visitor_kind : "unknown",
                     component_type.c_str());
        return false;
    }

    auto it = visitors.find(component_type);
    if (it != visitors.end() && it->second.owner != owner) {
        tc_log_error(
            "[NavMesh] refusing to replace %s bake visitor for component type '%s' owned by '%s' from owner '%s'",
            visitor_kind ? visitor_kind : "unknown",
            component_type.c_str(),
            it->second.owner.c_str(),
            owner.c_str());
        return false;
    }

    visitors[component_type] = VisitorRecord{std::move(visitor), owner};
    return true;
}

bool NavMeshBakeVisitorRegistry::unregister_visitor(
    VisitorMap& visitors,
    const std::string& component_type)
{
    return visitors.erase(component_type) > 0;
}

std::string NavMeshBakeVisitorRegistry::visitor_owner(
    const VisitorMap& visitors,
    const std::string& component_type)
{
    auto it = visitors.find(component_type);
    return it == visitors.end() ? std::string() : it->second.owner;
}

int NavMeshBakeVisitorRegistry::visit_component(
    Entity entity,
    CxxComponent* component,
    const char* component_type,
    const NavMeshBakeContext& context,
    NavMeshBakeInput& input) const
{
    if (!component) {
        return 0;
    }

    int visited = 0;
    const std::string type_name = component_type ? component_type : "";
    if (!type_name.empty() && type_name != "Component") {
        if (const NavMeshBakeVisitor* visitor = geometry_visitor(type_name)) {
            (*visitor)(entity, component, context, input);
            visited++;
        }
        if (const NavMeshBakeVisitor* visitor = link_visitor(type_name)) {
            (*visitor)(entity, component, context, input);
            visited++;
        }
        if (const NavMeshBakeVisitor* visitor = linear_visitor(type_name)) {
            (*visitor)(entity, component, context, input);
            visited++;
        }
        if (visited > 0) {
            return visited;
        }
    }

    return visited;
}

NavMeshBakeInput collect_navmesh_bake_input(
    const NavMeshBakeContext& context,
    const std::vector<Entity>& entities)
{
    NavMeshBakeInput input;
    NavMeshBakeVisitorRegistry& registry = NavMeshBakeVisitorRegistry::instance();
    registry.ensure_builtin_visitors_registered();

    for (Entity entity : entities) {
        if (!entity.valid()) {
            continue;
        }
        const size_t component_count = entity.component_count();
        for (size_t i = 0; i < component_count; ++i) {
            tc_component* tc = entity.component_at(i);
            if (!tc) {
                continue;
            }
            tc_component_try_link_declared_type(tc);
            const char* component_type = tc_component_type_name(tc);
            if (!component_type || component_type[0] == '\0') {
                continue;
            }
            CxxComponent* component = CxxComponent::from_tc(tc);
            if (!component) {
                continue;
            }
            registry.visit_component(entity, component, component_type, context, input);
        }
    }

    return input;
}

unsigned int stable_navmesh_source_user_id(Entity source, const std::string& local_id) {
    std::string key;
    if (source.valid() && source.uuid()) {
        key += source.uuid();
    }
    key += ":";
    key += local_id;

    uint32_t hash = 2166136261u;
    for (unsigned char c : key) {
        hash ^= c;
        hash *= 16777619u;
    }
    if (hash == 0) {
        hash = 1;
    }
    return hash;
}

unsigned char navmesh_detour_area_to_recast_area(int area_id) {
    const int clamped = std::clamp(area_id, 0, 62);
    if (clamped != area_id) {
        tc_log_warn("[NavMesh] geometry area_id=%d is outside supported Recast-backed range [0, 62], using %d",
                    area_id,
                    clamped);
    }
    return static_cast<unsigned char>(clamped + 1);
}

unsigned char navmesh_recast_area_to_detour_area(unsigned char recast_area, int fallback_area_id) {
    if (recast_area == RC_NULL_AREA) {
        return 0;
    }
    if (recast_area >= 1 && recast_area <= 63) {
        return static_cast<unsigned char>(recast_area - 1);
    }
    return static_cast<unsigned char>(std::clamp(fallback_area_id, 0, 63));
}

} // namespace termin
