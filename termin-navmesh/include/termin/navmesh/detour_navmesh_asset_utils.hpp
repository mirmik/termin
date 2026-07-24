#pragma once

#include <filesystem>
#include <string>
#include <vector>

#include <termin/entity/entity.hpp>
#include <termin/geom/vec3.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <termin/navmesh/tc_navmesh_handle.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>

namespace termin {

extern TERMIN_NAVMESH_COMPONENTS_API const char* const NAVMESH_DEBUG_PHASE;

TERMIN_NAVMESH_COMPONENTS_API std::string json_escape(const std::string& value);
TERMIN_NAVMESH_COMPONENTS_API std::string base64_encode(const unsigned char* data, int size);
TERMIN_NAVMESH_COMPONENTS_API std::vector<unsigned char> base64_decode(const std::string& input);
TERMIN_NAVMESH_COMPONENTS_API std::string sanitize_filename(std::string value);
TERMIN_NAVMESH_COMPONENTS_API std::string stable_uuid(const std::string& seed);
TERMIN_NAVMESH_COMPONENTS_API std::filesystem::path resolve_navmesh_output_path(const Entity& entity, const std::string& agent_type_name);
TERMIN_NAVMESH_COMPONENTS_API std::filesystem::path find_navmesh_asset_by_uuid(const std::filesystem::path& scene_path, const std::string& uuid);
TERMIN_NAVMESH_COMPONENTS_API TcMaterial get_or_create_navmesh_debug_material(TcMaterial& material);
TERMIN_NAVMESH_COMPONENTS_API const tc_shader_contract_desc&
navmesh_vertex_color_debug_shader_contract();
TERMIN_NAVMESH_COMPONENTS_API const tc_shader_contract_desc&
position_only_debug_shader_contract();
TERMIN_NAVMESH_COMPONENTS_API tc_material_phase* add_builtin_slang_debug_phase(
    TcMaterial& material,
    const char* shader_uuid,
    const char* shader_name,
    const char* phase_mark,
    int priority,
    const tc_render_state& state,
    const tc_shader_contract_desc& shader_contract);
TERMIN_NAVMESH_COMPONENTS_API TcMesh build_detour_debug_mesh(const std::filesystem::path& asset_path);
TERMIN_NAVMESH_COMPONENTS_API TcMesh build_detour_debug_mesh(const std::vector<std::vector<unsigned char>>& blobs);
TERMIN_NAVMESH_COMPONENTS_API TcMesh build_detour_debug_mesh(const TcNavMesh& navmesh);
TERMIN_NAVMESH_COMPONENTS_API bool load_detour_tile_blobs(const std::filesystem::path& asset_path, std::vector<std::vector<unsigned char>>& blobs);
TERMIN_NAVMESH_COMPONENTS_API bool load_detour_tile_blobs_from_navmesh(const TcNavMesh& navmesh,
                                                                       std::vector<std::vector<unsigned char>>& blobs);
TERMIN_NAVMESH_COMPONENTS_API Vec3f termin_to_recast(const Vec3f& p);
TERMIN_NAVMESH_COMPONENTS_API Vec3f recast_to_termin(const float p[3]);

} // namespace termin
