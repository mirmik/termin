#pragma once

#include <array>
#include <filesystem>
#include <string>
#include <vector>

#include <termin/entity/entity.hpp>
#include "../material/tc_material_handle.hpp"
#include <tgfx/tgfx_mesh_handle.hpp>
#include "tc_navmesh_handle.hpp"

namespace termin {

extern const char* const NAVMESH_DEBUG_PHASE;

std::string json_escape(const std::string& value);
std::string base64_encode(const unsigned char* data, int size);
std::vector<unsigned char> base64_decode(const std::string& input);
std::string sanitize_filename(std::string value);
std::string stable_uuid(const std::string& seed);
std::filesystem::path resolve_navmesh_output_path(const Entity& entity, const std::string& agent_type_name);
std::filesystem::path find_navmesh_asset_by_uuid(const std::filesystem::path& scene_path, const std::string& uuid);
TcMaterial get_or_create_navmesh_debug_material(TcMaterial& material);
TcMesh build_detour_debug_mesh(const std::filesystem::path& asset_path);
TcMesh build_detour_debug_mesh(const std::vector<std::vector<unsigned char>>& blobs);
TcMesh build_detour_debug_mesh(const TcNavMesh& navmesh);
bool load_detour_tile_blobs(const std::filesystem::path& asset_path, std::vector<std::vector<unsigned char>>& blobs);
bool load_detour_tile_blobs_from_navmesh(const TcNavMesh& navmesh,
                                         std::vector<std::vector<unsigned char>>& blobs);
std::array<float, 3> termin_to_recast(const std::array<float, 3>& p);
std::array<float, 3> recast_to_termin(const float p[3]);

} // namespace termin
