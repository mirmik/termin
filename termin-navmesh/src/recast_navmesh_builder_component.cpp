#include <termin/navmesh/recast_navmesh_builder_component.hpp>
#include <termin/navmesh/detour_navmesh_build.hpp>
#include <termin/navmesh/detour_navmesh_asset_utils.hpp>
#include <termin/navmesh/navmesh_keeper_component.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/tc_scene.hpp>
#include <array>
#include <cstring>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <sstream>
#include <set>
#include <utility>
#include <vector>
#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>

extern "C" {
#include <render/tc_render_category_flags.h>
}

namespace termin {

namespace {

constexpr const char* NAVMESH_DEBUG_SHADER_UUID = "termin-engine-navmesh-debug";

DetourOffMeshLinkData detour_links_from_bake_input(const NavMeshBakeInput& input) {
    DetourOffMeshLinkData links;
    for (const NavMeshOffMeshLinkRecord& record : input.off_mesh_links) {
        links.verts.insert(links.verts.end(), std::begin(record.start), std::end(record.start));
        links.verts.insert(links.verts.end(), std::begin(record.end), std::end(record.end));
        links.radii.push_back(record.radius);
        links.dirs.push_back(record.direction);
        links.areas.push_back(record.area_id);
        links.flags.push_back(record.flags);
        links.user_ids.push_back(record.user_id);
    }
    return links;
}

DetourLinearPathData detour_linear_paths_from_bake_input(const NavMeshBakeInput& input) {
    DetourLinearPathData paths;
    paths.segment_verts.reserve(input.linear_segments.size() * 6);
    paths.areas.reserve(input.linear_segments.size());
    paths.flags.reserve(input.linear_segments.size());
    paths.user_ids.reserve(input.linear_segments.size());
    paths.links.reserve(input.linear_links.size());

    for (const NavMeshLinearPathSegmentRecord& record : input.linear_segments) {
        paths.segment_verts.insert(paths.segment_verts.end(), std::begin(record.start), std::end(record.start));
        paths.segment_verts.insert(paths.segment_verts.end(), std::begin(record.end), std::end(record.end));
        paths.areas.push_back(record.area_id);
        paths.flags.push_back(record.flags);
        paths.user_ids.push_back(record.user_id);
    }

    for (const NavMeshLinearPathLinkRecord& record : input.linear_links) {
        DetourLinearLinkData link;
        link.from_segment = static_cast<unsigned short>(record.from_segment);
        link.to_segment = static_cast<unsigned short>(record.to_segment);
        link.from_t = record.from_t;
        link.to_t = record.to_t;
        link.flags = record.flags;
        paths.links.push_back(link);
    }

    return paths;
}

} // namespace

RecastNavMeshBuilderComponent::RecastNavMeshBuilderComponent()
    : CxxComponent("RecastNavMeshBuilderComponent")
{
    install_drawable_vtable(&_c);
}

void RecastNavMeshBuilderComponent::register_type() {
    register_component_type<RecastNavMeshBuilderComponent>(
        "RecastNavMeshBuilderComponent",
        "Component"
    );
    ComponentRegistry::instance().set_category("RecastNavMeshBuilderComponent", "Navigation");
    register_component_requirement("RecastNavMeshBuilderComponent", "NavMeshKeeperComponent");
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::agent_type_name,
        "RecastNavMeshBuilderComponent",
        "agent_type_name",
        "Agent Type",
        "agent_type"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::area_id,
        "RecastNavMeshBuilderComponent",
        "area_id",
        "Area",
        "navmesh_area"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::cell_size,
        "RecastNavMeshBuilderComponent",
        "cell_size",
        "Cell Size",
        "float",
        0.05,
        2.0,
        0.05
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::cell_height,
        "RecastNavMeshBuilderComponent",
        "cell_height",
        "Cell Height",
        "float",
        0.05,
        2.0,
        0.05
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::min_region_area,
        "RecastNavMeshBuilderComponent",
        "min_region_area",
        "Min Region Area",
        "int",
        0,
        100,
        1
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::merge_region_area,
        "RecastNavMeshBuilderComponent",
        "merge_region_area",
        "Merge Region Area",
        "int",
        0,
        100,
        1
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::max_edge_length,
        "RecastNavMeshBuilderComponent",
        "max_edge_length",
        "Max Edge Length",
        "float",
        0.0,
        50.0,
        0.5
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::max_simplification_error,
        "RecastNavMeshBuilderComponent",
        "max_simplification_error",
        "Max Simplification Error",
        "float",
        0.0,
        5.0,
        0.1
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::max_verts_per_poly,
        "RecastNavMeshBuilderComponent",
        "max_verts_per_poly",
        "Max Verts Per Poly",
        "int",
        3,
        6,
        1
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::build_detail_mesh,
        "RecastNavMeshBuilderComponent",
        "build_detail_mesh",
        "Build Detail Mesh",
        "bool"
    );
    tc::register_inspect_field_choices(
        &RecastNavMeshBuilderComponent::mesh_source,
        "RecastNavMeshBuilderComponent",
        "mesh_source",
        "Mesh Source",
        "enum",
        {
            {"0", "Current Mesh"},
            {"1", "All Descendants"},
        }
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::capture_heightfield,
        "RecastNavMeshBuilderComponent",
        "capture_heightfield",
        "Capture Heightfield (1)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::capture_compact,
        "RecastNavMeshBuilderComponent",
        "capture_compact",
        "Capture Compact (2)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::capture_contours,
        "RecastNavMeshBuilderComponent",
        "capture_contours",
        "Capture Contours (3)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::capture_poly_mesh,
        "RecastNavMeshBuilderComponent",
        "capture_poly_mesh",
        "Capture Poly Mesh (4)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::capture_detail_mesh,
        "RecastNavMeshBuilderComponent",
        "capture_detail_mesh",
        "Capture Detail Mesh (5)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::show_input_mesh,
        "RecastNavMeshBuilderComponent",
        "show_input_mesh",
        "Show Input Mesh (0)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::show_heightfield,
        "RecastNavMeshBuilderComponent",
        "show_heightfield",
        "Show Heightfield (1)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::show_regions,
        "RecastNavMeshBuilderComponent",
        "show_regions",
        "Show Regions (2)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::show_distance_field,
        "RecastNavMeshBuilderComponent",
        "show_distance_field",
        "Show Distance Field (3)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::show_contours,
        "RecastNavMeshBuilderComponent",
        "show_contours",
        "Show Contours (4)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::show_poly_mesh,
        "RecastNavMeshBuilderComponent",
        "show_poly_mesh",
        "Show Poly Mesh (5)",
        "bool"
    );
    tc::register_inspect_field(
        &RecastNavMeshBuilderComponent::show_detail_mesh,
        "RecastNavMeshBuilderComponent",
        "show_detail_mesh",
        "Show Detail Mesh (6)",
        "bool"
    );
    tc::register_inspect_button_method(
        "RecastNavMeshBuilderComponent",
        "build_btn",
        "Build NavMesh",
        &RecastNavMeshBuilderComponent::build_from_entity
    );
}

RecastNavMeshBuilderComponent::~RecastNavMeshBuilderComponent() {
    free_result(last_result);
}

void RecastNavMeshBuilderComponent::apply_agent_type(float height, float radius, float max_climb, float max_slope) {
    agent_height = height;
    agent_radius = radius;
    agent_max_climb = max_climb;
    agent_max_slope = max_slope;
    tc_log_info("[NavMesh] Applied agent type: height=%.2f, radius=%.2f, max_climb=%.2f, max_slope=%.1f",
        height, radius, max_climb, max_slope);
}

void RecastNavMeshBuilderComponent::clear_debug_data() {
    debug_data.clear();

    // Clear meshes (GPU resources are freed automatically via tc_mesh)
    _heightfield_mesh = TcMesh();
    _regions_mesh = TcMesh();
    _distance_field_mesh = TcMesh();
    _contours_mesh = TcMesh();
    _poly_mesh_debug = TcMesh();
    _detail_mesh_debug = TcMesh();
}

RecastBuildResult RecastNavMeshBuilderComponent::build(const float* verts, int nverts,
                                                        const int* tris, int ntris) {
    return build_internal(verts, nverts, tris, ntris, nullptr, true);
}

RecastBuildResult RecastNavMeshBuilderComponent::build_with_areas(
    const float* verts,
    int nverts,
    const int* tris,
    int ntris,
    const unsigned char* triangle_area_ids)
{
    return build_internal(verts, nverts, tris, ntris, triangle_area_ids, true);
}

RecastBuildResult RecastNavMeshBuilderComponent::build_internal(
    const float* verts,
    int nverts,
    const int* tris,
    int ntris,
    const unsigned char* triangle_area_ids,
    bool clear_bake_input)
{
    free_result(last_result);
    clear_debug_data();
    if (clear_bake_input) {
        last_bake_input = NavMeshBakeInput();
    }

    RecastNavMeshBuildConfig config;
    config.cell_size = cell_size;
    config.cell_height = cell_height;
    config.agent_height = agent_height;
    config.agent_radius = agent_radius;
    config.agent_max_climb = agent_max_climb;
    config.agent_max_slope = agent_max_slope;
    config.min_region_area = min_region_area;
    config.merge_region_area = merge_region_area;
    config.max_edge_length = max_edge_length;
    config.max_simplification_error = max_simplification_error;
    config.max_verts_per_poly = max_verts_per_poly;
    config.detail_sample_dist = detail_sample_dist;
    config.detail_sample_max_error = detail_sample_max_error;
    config.build_detail_mesh = build_detail_mesh;
    config.default_area_id = area_id;

    RecastNavMeshBuildDebugHooks debug_hooks;
    debug_hooks.build_input_mesh = [this](const float* v, int nv, const int* t, int nt) {
        build_input_mesh(v, nv, t, nt);
    };
    if (capture_heightfield) {
        debug_hooks.capture_heightfield = [this](rcHeightfield* hf) { capture_heightfield_data(hf); };
    }
    if (capture_compact) {
        debug_hooks.capture_compact = [this](rcCompactHeightfield* chf) { capture_compact_data(chf); };
    }
    if (capture_contours) {
        debug_hooks.capture_contours = [this](rcContourSet* cset) { capture_contour_data(cset); };
    }
    if (capture_poly_mesh) {
        debug_hooks.capture_poly_mesh = [this](rcPolyMesh* pmesh) { capture_poly_mesh_data(pmesh); };
    }
    if (capture_detail_mesh) {
        debug_hooks.capture_detail_mesh = [this](rcPolyMeshDetail* dmesh) { capture_detail_mesh_data(dmesh); };
    }

    RecastBuildResult result = build_recast_navmesh(
        verts,
        nverts,
        tris,
        ntris,
        triangle_area_ids,
        config,
        &debug_hooks);
    last_result = result;
    rebuild_debug_meshes();

    return result;
}

void RecastNavMeshBuilderComponent::free_result(RecastBuildResult& result) {
    free_recast_build_result(result);
}

DetourNavMeshTileBuildResult RecastNavMeshBuilderComponent::build_detour_tile_data(
    const RecastBuildResult& result
) {
    DetourOffMeshLinkData off_mesh_links = detour_links_from_bake_input(last_bake_input);
    DetourLinearPathData linear_paths = detour_linear_paths_from_bake_input(last_bake_input);
    DetourNavMeshBuildConfig detour_config;
    detour_config.area_id = area_id;
    detour_config.agent_height = agent_height;
    detour_config.agent_radius = agent_radius;
    detour_config.agent_max_climb = agent_max_climb;
    return build_detour_navmesh_tile_data(
        result,
        detour_config,
        off_mesh_links.count() > 0 ? &off_mesh_links : nullptr,
        linear_paths.count() > 0 ? &linear_paths : nullptr);
}

bool RecastNavMeshBuilderComponent::save_detour_asset(const RecastBuildResult& result) {
    rcPolyMesh* pmesh = result.poly_mesh;
    if (!result.success || !pmesh) {
        tc_log_error("RecastNavMeshBuilderComponent: cannot save Detour asset without a successful poly mesh");
        return false;
    }
    if (pmesh->nverts <= 0 || pmesh->npolys <= 0 || !pmesh->verts || !pmesh->polys) {
        tc_log_error("RecastNavMeshBuilderComponent: cannot save Detour asset from invalid poly mesh "
                     "(verts=%d polys=%d verts_ptr=%p polys_ptr=%p)",
                     pmesh ? pmesh->nverts : 0,
                     pmesh ? pmesh->npolys : 0,
                     pmesh ? static_cast<const void*>(pmesh->verts) : nullptr,
                     pmesh ? static_cast<const void*>(pmesh->polys) : nullptr);
        return false;
    }

    DetourOffMeshLinkData off_mesh_links = detour_links_from_bake_input(last_bake_input);
    DetourLinearPathData linear_paths = detour_linear_paths_from_bake_input(last_bake_input);
    DetourNavMeshBuildConfig detour_config;
    detour_config.area_id = area_id;
    detour_config.agent_height = agent_height;
    detour_config.agent_radius = agent_radius;
    detour_config.agent_max_climb = agent_max_climb;

    DetourNavMeshTileBuildResult tile = build_detour_navmesh_tile_data(
        result,
        detour_config,
        off_mesh_links.count() > 0 ? &off_mesh_links : nullptr,
        linear_paths.count() > 0 ? &linear_paths : nullptr);
    if (!tile.success) {
        tc_log_error("RecastNavMeshBuilderComponent: failed to build Detour navmesh tile: %s",
                     tile.error.c_str());
        return false;
    }

    const char* entity_name_c = entity().valid() && entity().name() ? entity().name() : "navmesh";
    std::string entity_name(entity_name_c);
    std::filesystem::path output_path = resolve_navmesh_output_path(entity(), agent_type_name);
    if (output_path.empty()) {
        tc_log_error("RecastNavMeshBuilderComponent: cannot save Detour navmesh: scene has no file path");
        return false;
    }
    std::error_code ec;
    std::filesystem::create_directories(output_path.parent_path(), ec);
    if (ec) {
        tc_log_error("RecastNavMeshBuilderComponent: failed to create directory '%s': %s",
                     output_path.parent_path().string().c_str(), ec.message().c_str());
        return false;
    }

    NavMeshKeeperComponent* keeper = entity().get_component<NavMeshKeeperComponent>();
    if (!keeper) {
        keeper = new NavMeshKeeperComponent();
        entity().add_component(keeper);
    }
    std::string uuid = keeper && !keeper->navmesh_uuid.empty()
        ? keeper->navmesh_uuid
        : stable_uuid(std::string(entity().uuid() ? entity().uuid() : entity_name) + ":" + agent_type_name);
    std::string asset_name = output_path.stem().string();

    const std::string blob = base64_encode(tile.data.data(), tile.data_size());

    std::ofstream out(output_path, std::ios::binary);
    if (!out) {
        tc_log_error("RecastNavMeshBuilderComponent: failed to open '%s' for writing",
                     output_path.string().c_str());
        return false;
    }

    out << "{\n";
    out << "  \"format\": \"termin.detour_navmesh\",\n";
    out << "  \"version\": 2,\n";
    out << "  \"name\": \"" << json_escape(asset_name) << "\",\n";
    out << "  \"agent_type\": \"" << json_escape(agent_type_name) << "\",\n";
    out << "  \"coordinate_system\": \"recast_y_up\",\n";
    out << "  \"source_entity_uuid\": \"" << json_escape(entity().uuid() ? entity().uuid() : "") << "\",\n";
    out << "  \"source_entity_name\": \"" << json_escape(entity_name) << "\",\n";
    out << "  \"build\": {\n";
    out << "    \"cell_size\": " << cell_size << ",\n";
    out << "    \"cell_height\": " << cell_height << ",\n";
    out << "    \"agent_height\": " << agent_height << ",\n";
    out << "    \"agent_radius\": " << agent_radius << ",\n";
    out << "    \"agent_max_climb\": " << agent_max_climb << ",\n";
    out << "    \"agent_max_slope\": " << agent_max_slope << ",\n";
    out << "    \"max_verts_per_poly\": " << max_verts_per_poly << ",\n";
    out << "    \"off_mesh_link_count\": " << off_mesh_links.count() << ",\n";
    out << "    \"linear_segment_count\": " << linear_paths.count() << ",\n";
    out << "    \"linear_link_count\": " << static_cast<int>(linear_paths.links.size()) << "\n";
    out << "  },\n";
    out << "  \"tiles\": [\n";
    out << "    {\n";
    out << "      \"x\": 0,\n";
    out << "      \"y\": 0,\n";
    out << "      \"layer\": 0,\n";
    out << "      \"data_encoding\": \"base64\",\n";
    out << "      \"data_size\": " << tile.data_size() << ",\n";
    out << "      \"data\": \"" << blob << "\"\n";
    out << "    }\n";
    out << "  ]\n";
    out << "}\n";
    out.close();

    if (!out) {
        tc_log_error("RecastNavMeshBuilderComponent: failed while writing '%s'",
                     output_path.string().c_str());
        return false;
    }

    const std::filesystem::path meta_path = output_path.string() + ".meta";
    std::ofstream meta(meta_path);
    if (meta) {
        meta << "{\n";
        meta << "  \"uuid\": \"" << json_escape(uuid) << "\",\n";
        meta << "  \"type\": \"navmesh\",\n";
        meta << "  \"format\": \"termin.detour_navmesh\",\n";
        meta << "  \"version\": 2\n";
        meta << "}\n";
    } else {
        tc_log_error("RecastNavMeshBuilderComponent: failed to write meta '%s'",
                     meta_path.string().c_str());
    }

    keeper->navmesh_uuid = uuid;
    keeper->invalidate_debug_mesh();

    tc_log_info("RecastNavMeshBuilderComponent: saved Detour navmesh '%s' (%d bytes, uuid=%s)",
                output_path.string().c_str(), tile.data_size(), uuid.c_str());
    return true;
}

// --- Drawable interface ---

std::set<std::string> RecastNavMeshBuilderComponent::get_phase_marks() const {
    std::set<std::string> marks;

    // Only participate in rendering if we have something to show
    if (show_input_mesh || show_heightfield || show_regions || show_distance_field ||
        show_contours || show_poly_mesh || show_detail_mesh) {
        marks.insert(NAVMESH_DEBUG_PHASE);
    }

    return marks;
}

bool RecastNavMeshBuilderComponent::collect_render_items(
    const tc_render_item_collect_context& context,
    tc_render_item_sink& sink)
{
    if (!sink.emit) {
        tc_log_error("[RecastNavMeshBuilderComponent] cannot emit render items: sink callback is null");
        return false;
    }
    const bool collect_all_phases =
        !context.phase_mark || context.phase_mark[0] == '\0';
    if (!collect_all_phases && std::string(context.phase_mark) != NAVMESH_DEBUG_PHASE) {
        return true;
    }
    if ((context.render_category_mask & TC_RENDER_CATEGORY_NAVMESH) == 0) {
        return true;
    }

    TcMaterial mat = get_debug_material();
    tc_material* material = mat.get();
    if (!material) {
        return true;
    }

    tc_material_phase* phases[TC_MATERIAL_MAX_PHASES];
    const size_t count = tc_material_get_phases_for_mark(
        material,
        NAVMESH_DEBUG_PHASE,
        phases,
        TC_MATERIAL_MAX_PHASES);
    if (count == 0) {
        return true;
    }

    struct Layer {
        bool visible;
        int geometry_id;
        TcMesh* mesh;
    };
    Layer layers[] = {
        {show_input_mesh, GEOMETRY_INPUT_MESH, &_input_mesh},
        {show_heightfield, GEOMETRY_HEIGHTFIELD, &_heightfield_mesh},
        {show_regions, GEOMETRY_REGIONS, &_regions_mesh},
        {show_distance_field, GEOMETRY_DISTANCE_FIELD, &_distance_field_mesh},
        {show_contours, GEOMETRY_CONTOURS, &_contours_mesh},
        {show_poly_mesh, GEOMETRY_POLY_MESH, &_poly_mesh_debug},
        {show_detail_mesh, GEOMETRY_DETAIL_MESH, &_detail_mesh_debug},
    };

    Mat44f model = get_model_matrix(entity());
    for (const Layer& layer : layers) {
        if (!layer.visible || !layer.mesh || !layer.mesh->is_valid()) {
            continue;
        }
        tc_mesh* mesh = layer.mesh->get();
        if (!mesh) {
            continue;
        }
        for (size_t i = 0; i < count; ++i) {
            tc_material_phase* phase = phases[i];
            tc_render_item item{};
            item.kind = TC_RENDER_ITEM_KIND_MESH;
            item.flags = TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX | TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE;
            item.component = tc_component_ptr();
            item.geometry_id = layer.geometry_id;
            item.material_phase = phase;
            item.material = mat.handle;
            item.material_phase_index = static_cast<size_t>(phase - material->phases);
            std::memcpy(item.model_matrix, model.data, sizeof(float) * 16);
            item.payload.mesh.mesh = mesh;
            item.payload.mesh.mesh_handle = layer.mesh->handle;
            item.payload.mesh.submesh_index = 0;
            if (!sink.emit(&item, sink.user_data)) {
                return false;
            }
        }
    }

    return true;
}

// --- Mesh generation ---

void RecastNavMeshBuilderComponent::rebuild_debug_meshes() {
    if (debug_data.heightfield) {
        build_heightfield_mesh();
    }
    if (debug_data.compact) {
        build_regions_mesh();
        build_distance_field_mesh();
    }
    if (debug_data.contours) {
        build_contours_mesh();
    }
    if (debug_data.poly_mesh) {
        build_poly_mesh_debug();
    }
    if (debug_data.detail_mesh) {
        build_detail_mesh_debug();
    }
}

void RecastNavMeshBuilderComponent::build_input_mesh(const float* verts, int nverts, const int* tris, int ntris) {
    if (!verts || nverts == 0 || !tris || ntris == 0) return;

    // Vertex layout: position (vec3) + color (vec4)
    // Debug shader attribute locations: 0=position, 1=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 1);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    const float input_color[4] = {0.3f, 0.6f, 0.9f, 0.5f};  // blue, semi-transparent

    std::vector<Vertex> vertices;
    vertices.reserve(nverts);

    // Vertices are in the builder bake frame: base translation/rotation removed,
    // but source scale is preserved in scene units.
    // Just convert from Recast (Y-up) back to termin (Z-up): (x, y, z) -> (x, z, y)
    // Note: these coords are relative to the builder frame, so they will be
    // transformed by entity's world matrix when drawn
    for (int i = 0; i < nverts; i++) {
        float rc_x = verts[i * 3 + 0];
        float rc_y = verts[i * 3 + 1];
        float rc_z = verts[i * 3 + 2];

        float tm_x = rc_x;
        float tm_y = rc_z;  // Recast Z -> termin Y
        float tm_z = rc_y;  // Recast Y -> termin Z

        if (i < 3) {
            tc_log_info("[NavMesh] InputMesh vert[%d]: recast=(%.2f, %.2f, %.2f) -> termin=(%.2f, %.2f, %.2f)",
                i, rc_x, rc_y, rc_z, tm_x, tm_y, tm_z);
        }

        vertices.push_back({
            {tm_x, tm_y, tm_z},
            {input_color[0], input_color[1], input_color[2], input_color[3]}
        });
    }

    // Copy indices
    std::vector<uint32_t> indices;
    indices.reserve(ntris * 3);
    for (int i = 0; i < ntris * 3; i++) {
        indices.push_back(static_cast<uint32_t>(tris[i]));
    }

    // Compute UUID
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_input");
    }

    _input_mesh = TcMesh(h);

    tc_log_info("[NavMesh] Input mesh debug: %d verts, %d tris", nverts, ntris);
}

void RecastNavMeshBuilderComponent::build_heightfield_mesh() {
    if (!debug_data.heightfield) return;

    const auto& hf = *debug_data.heightfield;
    if (hf.width == 0 || hf.height == 0) return;

    tc_log_info("[NavMesh] HF debug: Recast bmin=(%.2f, %.2f, %.2f) bmax not stored",
        hf.bmin[0], hf.bmin[1], hf.bmin[2]);
    tc_log_info("[NavMesh] HF debug: grid %dx%d, cs=%.3f ch=%.3f",
        hf.width, hf.height, hf.cs, hf.ch);

    // Vertex layout: position (vec3) + color (vec4)
    // Debug shader attribute locations: 0=position, 1=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 1);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Colors
    const float walkable_color[4] = {0.2f, 0.8f, 0.3f, 0.8f};    // green
    const float unwalkable_color[4] = {0.8f, 0.3f, 0.2f, 0.6f};  // red

    // For each cell, create a quad on top of each span
    // Convert from Recast (Y-up) back to termin (Z-up): swap Y and Z
    for (int rz = 0; rz < hf.height; rz++) {
        for (int rx = 0; rx < hf.width; rx++) {
            const auto& cell_spans = hf.spans[rz * hf.width + rx];

            for (const auto& span : cell_spans) {
                // Recast coordinates (Y-up)
                float rc_x0 = hf.bmin[0] + rx * hf.cs;
                float rc_x1 = rc_x0 + hf.cs;
                float rc_z0 = hf.bmin[2] + rz * hf.cs;
                float rc_z1 = rc_z0 + hf.cs;
                float rc_y = hf.bmin[1] + span.smax * hf.ch;

                // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
                float x0 = rc_x0, x1 = rc_x1;
                float y0 = rc_z0, y1 = rc_z1;  // Recast Z -> termin Y
                float z = rc_y;                 // Recast Y -> termin Z

                // Select color based on walkability
                const float* color = (span.area != 0) ? walkable_color : unwalkable_color;

                // Add 4 vertices for quad
                uint32_t base = static_cast<uint32_t>(vertices.size());

                vertices.push_back({{x0, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y1, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x0, y1, z}, {color[0], color[1], color[2], color[3]}});

                // Two triangles
                indices.push_back(base + 0);
                indices.push_back(base + 1);
                indices.push_back(base + 2);

                indices.push_back(base + 0);
                indices.push_back(base + 2);
                indices.push_back(base + 3);
            }
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_heightfield");
    }

    _heightfield_mesh = TcMesh(h);

    tc_log_info("[NavMesh] Heightfield mesh: %zu verts, %zu tris",
        vertices.size(), indices.size() / 3);
}

void RecastNavMeshBuilderComponent::build_regions_mesh() {
    if (!debug_data.compact) return;

    const auto& chf = *debug_data.compact;
    if (chf.width == 0 || chf.height == 0 || chf.span_count == 0) return;

    tc_log_info("[NavMesh] Regions debug: grid %dx%d, %d spans",
        chf.width, chf.height, chf.span_count);

    // Vertex layout: position (vec3) + color (vec4)
    // Debug shader attribute locations: 0=position, 1=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 1);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Generate color from region ID using golden ratio hue distribution
    auto region_color = [](uint16_t region) -> std::array<float, 4> {
        if (region == 0) {
            // Region 0 = no region (unwalkable or filtered out)
            return {0.2f, 0.2f, 0.2f, 0.3f};
        }
        // Golden ratio for even hue distribution
        float hue = std::fmod(region * 0.618033988749895f, 1.0f);
        float saturation = 0.7f;
        float value = 0.9f;

        // HSV to RGB conversion
        float h = hue * 6.0f;
        int i = static_cast<int>(h);
        float f = h - i;
        float p = value * (1.0f - saturation);
        float q = value * (1.0f - saturation * f);
        float t = value * (1.0f - saturation * (1.0f - f));

        float r, g, b;
        switch (i % 6) {
            case 0: r = value; g = t; b = p; break;
            case 1: r = q; g = value; b = p; break;
            case 2: r = p; g = value; b = t; break;
            case 3: r = p; g = q; b = value; break;
            case 4: r = t; g = p; b = value; break;
            default: r = value; g = p; b = q; break;
        }
        return {r, g, b, 0.8f};
    };

    // Iterate through all cells
    for (int rz = 0; rz < chf.height; rz++) {
        for (int rx = 0; rx < chf.width; rx++) {
            const auto& cell = chf.cells[rz * chf.width + rx];
            uint32_t first_span = cell.first;
            uint8_t span_count = cell.second;

            for (uint8_t s = 0; s < span_count; s++) {
                uint32_t span_idx = first_span + s;
                if (span_idx >= static_cast<uint32_t>(chf.span_count)) continue;

                uint16_t region = chf.regions[span_idx];
                uint16_t y_val = chf.y[span_idx];

                // Recast coordinates (Y-up)
                float rc_x0 = chf.bmin[0] + rx * chf.cs;
                float rc_x1 = rc_x0 + chf.cs;
                float rc_z0 = chf.bmin[2] + rz * chf.cs;
                float rc_z1 = rc_z0 + chf.cs;
                float rc_y = chf.bmin[1] + y_val * chf.ch;

                // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
                float x0 = rc_x0, x1 = rc_x1;
                float y0 = rc_z0, y1 = rc_z1;  // Recast Z -> termin Y
                float z = rc_y;                 // Recast Y -> termin Z

                // Get color for this region
                auto color = region_color(region);

                // Add 4 vertices for quad
                uint32_t base = static_cast<uint32_t>(vertices.size());

                vertices.push_back({{x0, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y1, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x0, y1, z}, {color[0], color[1], color[2], color[3]}});

                // Two triangles
                indices.push_back(base + 0);
                indices.push_back(base + 1);
                indices.push_back(base + 2);

                indices.push_back(base + 0);
                indices.push_back(base + 2);
                indices.push_back(base + 3);
            }
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_regions");
    }

    _regions_mesh = TcMesh(h);

    // Count unique regions
    std::set<uint16_t> unique_regions;
    for (uint16_t r : chf.regions) {
        if (r != 0) unique_regions.insert(r);
    }

    tc_log_info("[NavMesh] Regions mesh: %zu verts, %zu tris, %zu unique regions",
        vertices.size(), indices.size() / 3, unique_regions.size());
}

void RecastNavMeshBuilderComponent::build_distance_field_mesh() {
    if (!debug_data.compact) return;

    const auto& chf = *debug_data.compact;
    if (chf.width == 0 || chf.height == 0 || chf.span_count == 0) return;
    if (chf.distances.empty()) return;

    // Find max distance for normalization
    uint16_t max_dist = 1;
    for (uint16_t d : chf.distances) {
        if (d > max_dist) max_dist = d;
    }

    tc_log_info("[NavMesh] Distance field debug: grid %dx%d, %d spans, maxDist=%d",
        chf.width, chf.height, chf.span_count, max_dist);

    // Vertex layout: position (vec3) + color (vec4)
    // Debug shader attribute locations: 0=position, 1=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 1);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Color gradient: blue (boundary, dist=0) -> cyan -> green -> yellow -> red (center, max dist)
    auto distance_color = [max_dist](uint16_t dist) -> std::array<float, 4> {
        float t = static_cast<float>(dist) / static_cast<float>(max_dist);
        float r, g, b;

        if (t < 0.25f) {
            // Blue to Cyan
            float tt = t / 0.25f;
            r = 0.0f;
            g = tt;
            b = 1.0f;
        } else if (t < 0.5f) {
            // Cyan to Green
            float tt = (t - 0.25f) / 0.25f;
            r = 0.0f;
            g = 1.0f;
            b = 1.0f - tt;
        } else if (t < 0.75f) {
            // Green to Yellow
            float tt = (t - 0.5f) / 0.25f;
            r = tt;
            g = 1.0f;
            b = 0.0f;
        } else {
            // Yellow to Red
            float tt = (t - 0.75f) / 0.25f;
            r = 1.0f;
            g = 1.0f - tt;
            b = 0.0f;
        }

        return {r, g, b, 0.8f};
    };

    // Iterate through all cells
    for (int rz = 0; rz < chf.height; rz++) {
        for (int rx = 0; rx < chf.width; rx++) {
            const auto& cell = chf.cells[rz * chf.width + rx];
            uint32_t first_span = cell.first;
            uint8_t span_count = cell.second;

            for (uint8_t s = 0; s < span_count; s++) {
                uint32_t span_idx = first_span + s;
                if (span_idx >= static_cast<uint32_t>(chf.span_count)) continue;

                uint16_t dist = chf.distances[span_idx];
                uint16_t y_val = chf.y[span_idx];

                // Recast coordinates (Y-up)
                float rc_x0 = chf.bmin[0] + rx * chf.cs;
                float rc_x1 = rc_x0 + chf.cs;
                float rc_z0 = chf.bmin[2] + rz * chf.cs;
                float rc_z1 = rc_z0 + chf.cs;
                float rc_y = chf.bmin[1] + y_val * chf.ch;

                // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
                float x0 = rc_x0, x1 = rc_x1;
                float y0 = rc_z0, y1 = rc_z1;  // Recast Z -> termin Y
                float z = rc_y;                 // Recast Y -> termin Z

                // Get color for this distance
                auto color = distance_color(dist);

                // Add 4 vertices for quad
                uint32_t base = static_cast<uint32_t>(vertices.size());

                vertices.push_back({{x0, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y0, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x1, y1, z}, {color[0], color[1], color[2], color[3]}});
                vertices.push_back({{x0, y1, z}, {color[0], color[1], color[2], color[3]}});

                // Two triangles
                indices.push_back(base + 0);
                indices.push_back(base + 1);
                indices.push_back(base + 2);

                indices.push_back(base + 0);
                indices.push_back(base + 2);
                indices.push_back(base + 3);
            }
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_distance_field");
    }

    _distance_field_mesh = TcMesh(h);

    tc_log_info("[NavMesh] Distance field mesh: %zu verts, %zu tris",
        vertices.size(), indices.size() / 3);
}

void RecastNavMeshBuilderComponent::build_contours_mesh() {
    if (!debug_data.contours) return;

    const auto& cset = *debug_data.contours;
    if (cset.contours.empty()) return;

    tc_log_info("[NavMesh] Contours debug: %zu contours", cset.contours.size());

    // Vertex layout: position (vec3) + color (vec4)
    // Debug shader attribute locations: 0=position, 1=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 1);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Generate color from region ID using golden ratio hue distribution
    auto region_color = [](uint16_t region) -> std::array<float, 4> {
        if (region == 0) {
            return {0.5f, 0.5f, 0.5f, 1.0f};
        }
        float hue = std::fmod(region * 0.618033988749895f, 1.0f);
        float saturation = 0.8f;
        float value = 1.0f;

        // HSV to RGB conversion
        float h = hue * 6.0f;
        int i = static_cast<int>(h);
        float f = h - i;
        float p = value * (1.0f - saturation);
        float q = value * (1.0f - saturation * f);
        float t = value * (1.0f - saturation * (1.0f - f));

        float r, g, b;
        switch (i % 6) {
            case 0: r = value; g = t; b = p; break;
            case 1: r = q; g = value; b = p; break;
            case 2: r = p; g = value; b = t; break;
            case 3: r = p; g = q; b = value; break;
            case 4: r = t; g = p; b = value; break;
            default: r = value; g = p; b = q; break;
        }
        return {r, g, b, 1.0f};
    };

    for (const auto& contour : cset.contours) {
        if (contour.nverts < 2) continue;

        auto color = region_color(contour.region);

        // Contour vertices are stored as (x, y, z, region_id) in voxel space
        // 4 int32 values per vertex
        for (int i = 0; i < contour.nverts; i++) {
            int vx = contour.verts[i * 4 + 0];
            int vy = contour.verts[i * 4 + 1];
            int vz = contour.verts[i * 4 + 2];

            // Convert voxel coords to Recast world coords (Y-up)
            float rc_x = cset.bmin[0] + vx * cset.cs;
            float rc_y = cset.bmin[1] + vy * cset.ch;
            float rc_z = cset.bmin[2] + vz * cset.cs;

            // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
            float tm_x = rc_x;
            float tm_y = rc_z;  // Recast Z -> termin Y
            float tm_z = rc_y;  // Recast Y -> termin Z

            vertices.push_back({{tm_x, tm_y, tm_z}, {color[0], color[1], color[2], color[3]}});
        }
    }

    if (vertices.empty()) return;

    // Build line indices: each contour is a closed loop
    uint32_t vertex_offset = 0;
    for (const auto& contour : cset.contours) {
        if (contour.nverts < 2) continue;

        for (int i = 0; i < contour.nverts; i++) {
            int next = (i + 1) % contour.nverts;
            indices.push_back(vertex_offset + i);
            indices.push_back(vertex_offset + next);
        }
        vertex_offset += contour.nverts;
    }

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_contours");
        m->draw_mode = TC_DRAW_LINES;
    }

    _contours_mesh = TcMesh(h);

    tc_log_info("[NavMesh] Contours mesh: %zu verts, %zu lines",
        vertices.size(), indices.size() / 2);
}

void RecastNavMeshBuilderComponent::build_poly_mesh_debug() {
    if (!debug_data.poly_mesh) return;

    const auto& pmesh = *debug_data.poly_mesh;
    if (pmesh.nverts == 0 || pmesh.npolys == 0) return;

    tc_log_info("[NavMesh] PolyMesh debug: %d verts, %d polys (nvp=%d)",
        pmesh.nverts, pmesh.npolys, pmesh.nvp);

    // Vertex layout: position (vec3) + color (vec4)
    // Debug shader attribute locations: 0=position, 1=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 1);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Generate color from region ID using golden ratio hue distribution
    auto region_color = [](uint16_t region) -> std::array<float, 4> {
        if (region == 0) {
            return {0.3f, 0.3f, 0.3f, 0.8f};
        }
        float hue = std::fmod(region * 0.618033988749895f, 1.0f);
        float saturation = 0.6f;
        float value = 0.9f;

        // HSV to RGB conversion
        float h = hue * 6.0f;
        int i = static_cast<int>(h);
        float f = h - i;
        float p = value * (1.0f - saturation);
        float q = value * (1.0f - saturation * f);
        float t = value * (1.0f - saturation * (1.0f - f));

        float r, g, b;
        switch (i % 6) {
            case 0: r = value; g = t; b = p; break;
            case 1: r = q; g = value; b = p; break;
            case 2: r = p; g = value; b = t; break;
            case 3: r = p; g = q; b = value; break;
            case 4: r = t; g = p; b = value; break;
            default: r = value; g = p; b = q; break;
        }
        return {r, g, b, 0.8f};
    };

        // For each polygon, triangulate using fan triangulation
    for (int p = 0; p < pmesh.npolys; p++) {
        const uint16_t* poly = &pmesh.polys[p * pmesh.nvp * 2];

        // Count vertices in this polygon (stop at 0xFFFF)
        int nv = 0;
        for (int i = 0; i < pmesh.nvp; i++) {
            if (poly[i] == 0xFFFF) break;
            nv++;
        }
        if (nv < 3) continue;

        // Color by polygon index to see individual polygons (not by region)
        auto color = region_color(static_cast<uint16_t>(p + 1));

        // Add vertices for this polygon
        uint32_t base_vertex = static_cast<uint32_t>(vertices.size());

        for (int i = 0; i < nv; i++) {
            uint16_t vi = poly[i];
            // Vertices are stored as (x, y, z) uint16 in voxel coords
            uint16_t vx = pmesh.verts[vi * 3 + 0];
            uint16_t vy = pmesh.verts[vi * 3 + 1];
            uint16_t vz = pmesh.verts[vi * 3 + 2];

            // Convert voxel coords to Recast world coords (Y-up)
            float rc_x = pmesh.bmin[0] + vx * pmesh.cs;
            float rc_y = pmesh.bmin[1] + vy * pmesh.ch;
            float rc_z = pmesh.bmin[2] + vz * pmesh.cs;

            // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
            float tm_x = rc_x;
            float tm_y = rc_z;  // Recast Z -> termin Y
            float tm_z = rc_y;  // Recast Y -> termin Z

            vertices.push_back({{tm_x, tm_y, tm_z}, {color[0], color[1], color[2], color[3]}});
        }

        // Fan triangulation: (0, 1, 2), (0, 2, 3), (0, 3, 4), ...
        for (int i = 2; i < nv; i++) {
            indices.push_back(base_vertex);
            indices.push_back(base_vertex + i - 1);
            indices.push_back(base_vertex + i);
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* m = tc_mesh_get(h);
    if (!m) return;

    // Set data if mesh is new
    if (m->vertex_count == 0) {
        tc_mesh_set_data(m,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_poly_mesh");
    }

    _poly_mesh_debug = TcMesh(h);

    tc_log_info("[NavMesh] PolyMesh debug mesh: %zu verts, %zu tris",
        vertices.size(), indices.size() / 3);
}

void RecastNavMeshBuilderComponent::build_detail_mesh_debug() {
    if (!debug_data.detail_mesh) return;

    const auto& dmesh = *debug_data.detail_mesh;
    if (dmesh.nmeshes == 0 || dmesh.nverts == 0 || dmesh.ntris == 0) return;

    tc_log_info("[NavMesh] DetailMesh debug: %d meshes, %d verts, %d tris",
        dmesh.nmeshes, dmesh.nverts, dmesh.ntris);

    // Vertex layout: position (vec3) + color (vec4)
    // Debug shader attribute locations: 0=position, 1=color
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 1);

    struct Vertex {
        float pos[3];
        float color[4];
    };

    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;

    // Generate color from mesh index using golden ratio hue distribution
    auto mesh_color = [](int mesh_idx) -> std::array<float, 4> {
        float hue = std::fmod(mesh_idx * 0.618033988749895f, 1.0f);
        float saturation = 0.5f;
        float value = 1.0f;

        // HSV to RGB conversion
        float h = hue * 6.0f;
        int i = static_cast<int>(h);
        float f = h - i;
        float p = value * (1.0f - saturation);
        float q = value * (1.0f - saturation * f);
        float t = value * (1.0f - saturation * (1.0f - f));

        float r, g, b;
        switch (i % 6) {
            case 0: r = value; g = t; b = p; break;
            case 1: r = q; g = value; b = p; break;
            case 2: r = p; g = value; b = t; break;
            case 3: r = p; g = q; b = value; break;
            case 4: r = t; g = p; b = value; break;
            default: r = value; g = p; b = q; break;
        }
        return {r, g, b, 0.9f};
    };

    // Process each sub-mesh (one per polygon)
    for (int m = 0; m < dmesh.nmeshes; m++) {
        // meshes array: (vert_base, vert_count, tri_base, tri_count) per mesh
        uint32_t vert_base = dmesh.meshes[m * 4 + 0];
        uint32_t vert_count = dmesh.meshes[m * 4 + 1];
        uint32_t tri_base = dmesh.meshes[m * 4 + 2];
        uint32_t tri_count = dmesh.meshes[m * 4 + 3];

        if (vert_count == 0 || tri_count == 0) continue;

        auto color = mesh_color(m);
        uint32_t base_vertex = static_cast<uint32_t>(vertices.size());

        // Add vertices for this sub-mesh
        // Detail mesh vertices are already in Recast world coords (float, Y-up)
        for (uint32_t v = 0; v < vert_count; v++) {
            uint32_t vi = vert_base + v;
            float rc_x = dmesh.verts[vi * 3 + 0];
            float rc_y = dmesh.verts[vi * 3 + 1];
            float rc_z = dmesh.verts[vi * 3 + 2];

            // Convert to termin (Z-up): (x, y, z) -> (x, z, y)
            float tm_x = rc_x;
            float tm_y = rc_z;  // Recast Z -> termin Y
            float tm_z = rc_y;  // Recast Y -> termin Z

            vertices.push_back({{tm_x, tm_y, tm_z}, {color[0], color[1], color[2], color[3]}});
        }

        // Add triangles for this sub-mesh
        // Detail triangles: (v0, v1, v2, flags) as uint8, indices are local to sub-mesh
        for (uint32_t t = 0; t < tri_count; t++) {
            uint32_t ti = tri_base + t;
            uint8_t v0 = dmesh.tris[ti * 4 + 0];
            uint8_t v1 = dmesh.tris[ti * 4 + 1];
            uint8_t v2 = dmesh.tris[ti * 4 + 2];
            // uint8_t flags = dmesh.tris[ti * 4 + 3]; // not used for visualization

            indices.push_back(base_vertex + v0);
            indices.push_back(base_vertex + v1);
            indices.push_back(base_vertex + v2);
        }
    }

    if (vertices.empty()) return;

    // Compute UUID from vertex data
    size_t vertices_size = vertices.size() * sizeof(Vertex);
    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices_size, indices.data(), indices.size(), uuid);

    // Get or create mesh
    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* mesh = tc_mesh_get(h);
    if (!mesh) return;

    // Set data if mesh is new
    if (mesh->vertex_count == 0) {
        tc_mesh_set_data(mesh,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_debug_detail_mesh");
    }

    _detail_mesh_debug = TcMesh(h);

    tc_log_info("[NavMesh] DetailMesh debug mesh: %zu verts, %zu tris",
        vertices.size(), indices.size() / 3);
}

TcMaterial RecastNavMeshBuilderComponent::get_debug_material() {
    if (!_debug_material.is_valid()) {
        // Create material programmatically with vertex color shader
        _debug_material = TcMaterial::create("navmesh_debug_material");
        if (!_debug_material.is_valid()) {
            tc_log_error("[NavMesh] Failed to create debug material");
            return _debug_material;
        }

        tc_render_state state = tc_render_state_opaque();
        state.depth_test = 1;
        state.depth_write = 0;
        state.cull = 0;  // No culling for debug mesh
        state.blend = 0;

        tc_material_phase* phase = add_builtin_slang_debug_phase(
            _debug_material,
            NAVMESH_DEBUG_SHADER_UUID,
            "navmesh_debug_shader",
            NAVMESH_DEBUG_PHASE,
            0,  // priority
            state
        );

        if (!phase) {
            tc_log_error("[NavMesh] Failed to add phase to debug material");
        }
    }
    return _debug_material;
}

// --- Capture functions ---

void RecastNavMeshBuilderComponent::capture_heightfield_data(rcHeightfield* hf) {
    if (!hf) return;

    debug_data.heightfield = RecastDebugData::Heightfield{};
    auto& data = *debug_data.heightfield;
    data.width = hf->width;
    data.height = hf->height;
    data.cs = hf->cs;
    data.ch = hf->ch;
    rcVcopy(data.bmin, hf->bmin);
    rcVcopy(data.bmax, hf->bmax);

    data.spans.resize(hf->width * hf->height);

    for (int z = 0; z < hf->height; z++) {
        for (int x = 0; x < hf->width; x++) {
            auto& cell_spans = data.spans[z * hf->width + x];
            for (rcSpan* s = hf->spans[z * hf->width + x]; s; s = s->next) {
                RecastSpan span;
                span.smin = static_cast<uint16_t>(s->smin);
                span.smax = static_cast<uint16_t>(s->smax);
                span.area = static_cast<uint8_t>(s->area);
                cell_spans.push_back(span);
            }
        }
    }
}

void RecastNavMeshBuilderComponent::capture_compact_data(rcCompactHeightfield* chf) {
    if (!chf) return;

    debug_data.compact = RecastDebugData::CompactHeightfield{};
    auto& data = *debug_data.compact;
    data.width = chf->width;
    data.height = chf->height;
    data.span_count = chf->spanCount;
    data.cs = chf->cs;
    data.ch = chf->ch;
    rcVcopy(data.bmin, chf->bmin);
    rcVcopy(data.bmax, chf->bmax);

    // Per-span data
    data.y.resize(chf->spanCount);
    data.distances.resize(chf->spanCount);
    data.regions.resize(chf->spanCount);
    data.areas.resize(chf->spanCount);

    for (int i = 0; i < chf->spanCount; i++) {
        data.y[i] = chf->spans[i].y;
        data.distances[i] = chf->dist ? chf->dist[i] : 0;
        data.regions[i] = chf->spans[i].reg;
        data.areas[i] = chf->areas[i];
    }

    // Cell index
    data.cells.resize(chf->width * chf->height);
    for (int i = 0; i < chf->width * chf->height; i++) {
        data.cells[i] = {static_cast<unsigned int>(chf->cells[i].index), static_cast<uint8_t>(chf->cells[i].count)};
    }
}

void RecastNavMeshBuilderComponent::capture_contour_data(rcContourSet* cset) {
    if (!cset) return;

    debug_data.contours = RecastDebugData::ContourSet{};
    auto& data = *debug_data.contours;
    data.cs = cset->cs;
    data.ch = cset->ch;
    rcVcopy(data.bmin, cset->bmin);
    rcVcopy(data.bmax, cset->bmax);

    data.contours.resize(cset->nconts);
    for (int i = 0; i < cset->nconts; i++) {
        const rcContour& src = cset->conts[i];
        RecastDebugData::Contour& dst = data.contours[i];

        dst.region = src.reg;
        dst.area = src.area;

        // Simplified vertices
        dst.nverts = src.nverts;
        dst.verts.resize(src.nverts * 4);
        memcpy(dst.verts.data(), src.verts, src.nverts * 4 * sizeof(int));

        // Raw vertices
        dst.nraw_verts = src.nrverts;
        dst.raw_verts.resize(src.nrverts * 4);
        memcpy(dst.raw_verts.data(), src.rverts, src.nrverts * 4 * sizeof(int));
    }
}

void RecastNavMeshBuilderComponent::capture_poly_mesh_data(rcPolyMesh* pmesh) {
    if (!pmesh) return;

    debug_data.poly_mesh = RecastDebugData::PolyMesh{};
    auto& data = *debug_data.poly_mesh;
    data.nverts = pmesh->nverts;
    data.npolys = pmesh->npolys;
    data.nvp = pmesh->nvp;
    data.cs = pmesh->cs;
    data.ch = pmesh->ch;
    rcVcopy(data.bmin, pmesh->bmin);
    rcVcopy(data.bmax, pmesh->bmax);

    // Vertices
    data.verts.resize(pmesh->nverts * 3);
    memcpy(data.verts.data(), pmesh->verts, pmesh->nverts * 3 * sizeof(uint16_t));

    // Polygons
    data.polys.resize(pmesh->npolys * pmesh->nvp * 2);
    memcpy(data.polys.data(), pmesh->polys, pmesh->npolys * pmesh->nvp * 2 * sizeof(uint16_t));

    // Per-polygon data
    data.regions.resize(pmesh->npolys);
    data.flags.resize(pmesh->npolys);
    data.areas.resize(pmesh->npolys);
    memcpy(data.regions.data(), pmesh->regs, pmesh->npolys * sizeof(uint16_t));
    memcpy(data.flags.data(), pmesh->flags, pmesh->npolys * sizeof(uint16_t));
    memcpy(data.areas.data(), pmesh->areas, pmesh->npolys * sizeof(uint8_t));
}

void RecastNavMeshBuilderComponent::capture_detail_mesh_data(rcPolyMeshDetail* dmesh) {
    if (!dmesh) return;

    debug_data.detail_mesh = RecastDebugData::PolyMeshDetail{};
    auto& data = *debug_data.detail_mesh;
    data.nmeshes = dmesh->nmeshes;
    data.nverts = dmesh->nverts;
    data.ntris = dmesh->ntris;

    // Meshes: (vert_base, vert_count, tri_base, tri_count)
    data.meshes.resize(dmesh->nmeshes * 4);
    memcpy(data.meshes.data(), dmesh->meshes, dmesh->nmeshes * 4 * sizeof(uint32_t));

    // Vertices
    data.verts.resize(dmesh->nverts * 3);
    memcpy(data.verts.data(), dmesh->verts, dmesh->nverts * 3 * sizeof(float));

    // Triangles
    data.tris.resize(dmesh->ntris * 4);
    memcpy(data.tris.data(), dmesh->tris, dmesh->ntris * 4 * sizeof(uint8_t));
}

} // namespace termin
