#include "detour_navmesh_asset_utils.hpp"

#include <termin/tc_scene.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <DetourNavMesh.h>
#include <DetourStatus.h>
#include <inspect/tc_kind_cpp.hpp>
#include <tcbase/trent/json.h>
#include <algorithm>
#include <any>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iterator>
#include <memory>
#include <sstream>
#include <tcbase/tc_log.hpp>

namespace termin {

const char* const NAVMESH_DEBUG_PHASE = "editor_debug";

namespace {

constexpr const char* NAVMESH_DEBUG_SHADER_UUID = "termin-engine-navmesh-debug";

char* duplicate_c_string(const char* value) {
    if (!value) return nullptr;
    const size_t size = std::strlen(value) + 1;
    char* copy = static_cast<char*>(std::malloc(size));
    if (!copy) return nullptr;
    std::memcpy(copy, value, size);
    return copy;
}

bool set_debug_shader_entries(tc_material_phase* phase, const char* shader_name) {
    if (!phase || tc_shader_handle_is_invalid(phase->shader)) {
        tc_log_error("[NavMesh] cannot set debug shader entries for '%s': phase shader is invalid", shader_name);
        return false;
    }

    TcShader shader(phase->shader);
    tc_shader* raw = shader.get();
    if (!raw) {
        tc_log_error("[NavMesh] cannot set debug shader entries for '%s': shader data is missing", shader_name);
        return false;
    }

    free(raw->vertex_entry);
    raw->vertex_entry = duplicate_c_string("vs_main");
    if (!raw->vertex_entry) {
        tc_log_error("[NavMesh] failed to set vertex entry for debug shader '%s'", shader_name);
        return false;
    }

    free(raw->fragment_entry);
    raw->fragment_entry = duplicate_c_string("fs_main");
    if (!raw->fragment_entry) {
        tc_log_error("[NavMesh] failed to set fragment entry for debug shader '%s'", shader_name);
        return false;
    }

    return true;
}

struct NavMeshHandleKindRegistrar {
    NavMeshHandleKindRegistrar() {
        tc::KindRegistryCpp::instance().register_kind(
            "navmesh_handle",
            [](const std::any& value) -> tc_value {
                const std::string uuid =
                    value.type() == typeid(std::string) ? std::any_cast<std::string>(value) : std::string();
                tc_value result = tc_value_dict_new();
                tc_value_dict_set(&result, "uuid", tc_value_string(uuid.c_str()));
                tc_value_dict_set(&result, "name", tc_value_string(""));
                return result;
            },
            [](const tc_value* value, void*) -> std::any {
                if (!value || value->type == TC_VALUE_NIL) {
                    return std::string();
                }
                if (value->type == TC_VALUE_STRING && value->data.s) {
                    return std::string(value->data.s);
                }
                if (value->type == TC_VALUE_DICT) {
                    tc_value* uuid = tc_value_dict_get(const_cast<tc_value*>(value), "uuid");
                    if (uuid && uuid->type == TC_VALUE_STRING && uuid->data.s) {
                        return std::string(uuid->data.s);
                    }
                }
                return std::string();
            }
        );
    }
};

NavMeshHandleKindRegistrar navmesh_handle_kind_registrar;


} // namespace

tc_material_phase* add_builtin_slang_debug_phase(
    TcMaterial& material,
    const char* shader_uuid,
    const char* shader_name,
    const char* phase_mark,
    int priority,
    const tc_render_state& state
) {
    if (!material.is_valid()) {
        tc_log_error("[NavMesh] cannot add debug shader '%s': material is invalid", shader_name);
        return nullptr;
    }

    const std::string vertex_source =
        tgfx::load_builtin_shader_stage_source_from_catalog(shader_uuid, "vertex");
    const std::string fragment_source =
        tgfx::load_builtin_shader_stage_source_from_catalog(shader_uuid, "fragment");
    if (vertex_source.empty() || fragment_source.empty()) {
        tc_log_error("[NavMesh] Failed to load debug shader '%s'", shader_uuid);
        return nullptr;
    }

    tc_material_phase* phase = material.add_phase_from_sources(
        vertex_source.c_str(),
        fragment_source.c_str(),
        nullptr,
        shader_name,
        phase_mark,
        priority,
        state,
        nullptr,
        TC_SHADER_LANGUAGE_SLANG,
        TC_SHADER_ARTIFACT_REQUIRED
    );

    if (!phase) {
        tc_log_error("[NavMesh] Failed to add phase to debug material for shader '%s'", shader_name);
        return nullptr;
    }

    if (!set_debug_shader_entries(phase, shader_name)) {
        tc_shader_handle shader = phase->shader;
        phase->shader = tc_shader_handle_invalid();
        if (!tc_shader_handle_is_invalid(shader)) {
            tc_shader_destroy(shader);
        }
        return nullptr;
    }

    return phase;
}

std::string json_escape(const std::string& value) {
    std::ostringstream out;
    for (char ch : value) {
        switch (ch) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (static_cast<unsigned char>(ch) < 0x20) {
                    out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                        << static_cast<int>(static_cast<unsigned char>(ch));
                } else {
                    out << ch;
                }
                break;
        }
    }
    return out.str();
}

std::string base64_encode(const unsigned char* data, int size) {
    static constexpr char alphabet[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    out.reserve(((size + 2) / 3) * 4);

    for (int i = 0; i < size; i += 3) {
        unsigned int v = static_cast<unsigned int>(data[i]) << 16;
        if (i + 1 < size) v |= static_cast<unsigned int>(data[i + 1]) << 8;
        if (i + 2 < size) v |= static_cast<unsigned int>(data[i + 2]);

        out.push_back(alphabet[(v >> 18) & 0x3f]);
        out.push_back(alphabet[(v >> 12) & 0x3f]);
        out.push_back((i + 1 < size) ? alphabet[(v >> 6) & 0x3f] : '=');
        out.push_back((i + 2 < size) ? alphabet[v & 0x3f] : '=');
    }
    return out;
}

std::vector<unsigned char> base64_decode(const std::string& input) {
    static constexpr signed char invalid = -1;
    static constexpr signed char padding = -2;
    signed char table[256];
    std::fill(std::begin(table), std::end(table), invalid);

    const char* alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    for (int i = 0; alphabet[i]; ++i) {
        table[static_cast<unsigned char>(alphabet[i])] = static_cast<signed char>(i);
    }
    table[static_cast<unsigned char>('=')] = padding;

    std::vector<unsigned char> out;
    int value = 0;
    int bits = -8;
    for (unsigned char ch : input) {
        if (ch == ' ' || ch == '\n' || ch == '\r' || ch == '\t') {
            continue;
        }
        signed char decoded = table[ch];
        if (decoded == padding) {
            break;
        }
        if (decoded == invalid) {
            return {};
        }
        value = (value << 6) | decoded;
        bits += 6;
        if (bits >= 0) {
            out.push_back(static_cast<unsigned char>((value >> bits) & 0xff));
            bits -= 8;
        }
    }
    return out;
}

std::string sanitize_filename(std::string value) {
    if (value.empty()) {
        value = "navmesh";
    }
    for (char& ch : value) {
        const bool ok =
            (ch >= 'a' && ch <= 'z') ||
            (ch >= 'A' && ch <= 'Z') ||
            (ch >= '0' && ch <= '9') ||
            ch == '_' || ch == '-';
        if (!ok) {
            ch = '_';
        }
    }
    return value;
}

std::string entity_path_string(Entity entity) {
    std::vector<std::string> parts;
    while (entity.valid()) {
        const char* name = entity.name();
        parts.push_back(sanitize_filename(name && name[0] ? std::string(name) : std::string("entity")));
        entity = entity.parent();
    }
    std::reverse(parts.begin(), parts.end());

    std::ostringstream out;
    for (size_t i = 0; i < parts.size(); ++i) {
        if (i > 0) {
            out << "__";
        }
        out << parts[i];
    }
    return out.str();
}

uint64_t fnv1a64(const std::string& value) {
    uint64_t hash = 1469598103934665603ull;
    for (unsigned char ch : value) {
        hash ^= ch;
        hash *= 1099511628211ull;
    }
    return hash;
}

std::string stable_uuid(const std::string& seed) {
    const uint64_t a = fnv1a64(seed);
    const uint64_t b = fnv1a64("termin-navmesh:" + seed);
    std::ostringstream out;
    out << std::hex << std::setfill('0')
        << std::setw(8) << static_cast<uint32_t>(a >> 32) << "-"
        << std::setw(4) << static_cast<uint16_t>(a >> 16) << "-"
        << std::setw(4) << static_cast<uint16_t>(a) << "-"
        << std::setw(4) << static_cast<uint16_t>(b >> 48) << "-"
        << std::setw(12) << (b & 0x0000ffffffffffffull);
    return out.str();
}

std::filesystem::path resolve_navmesh_output_path(const Entity& entity, const std::string& agent_type_name) {
    TcSceneRef scene = entity.scene();
    if (!scene.valid()) {
        return {};
    }

    std::string scene_path = scene.source_path();
    if (scene_path.empty()) {
        return {};
    }

    std::filesystem::path scene_file_path(scene_path);
    std::string scene_stem = scene_file_path.stem().string();
    if (scene_stem.empty()) {
        scene_stem = scene.name();
    }

    const std::string file_name =
        entity_path_string(entity) + "-" + sanitize_filename(agent_type_name) + ".navmesh";

    return scene_file_path.parent_path()
        / "navmeshes"
        / sanitize_filename(scene_stem)
        / file_name;
}

std::filesystem::path find_navmesh_asset_by_uuid(const std::filesystem::path& scene_path,
                                                 const std::string& uuid) {
    if (uuid.empty()) {
        return {};
    }

    std::filesystem::path root = scene_path.parent_path() / "navmeshes";
    std::error_code ec;
    if (!std::filesystem::exists(root, ec)) {
        return {};
    }

    std::filesystem::recursive_directory_iterator it(root, ec);
    std::filesystem::recursive_directory_iterator end;
    while (!ec && it != end) {
        const std::filesystem::path path = it->path();
        if (it->is_regular_file(ec) && path.extension() == ".meta") {
            try {
                nos::trent meta = nos::json::parse_file(path.string());
                if (meta.is_dict() && meta.contains("uuid") &&
                    meta["uuid"].is_string() && meta["uuid"].as_string() == uuid) {
                    std::filesystem::path asset_path = path;
                    asset_path.replace_extension("");
                    return asset_path;
                }
            } catch (const std::exception& e) {
                tc_log_warn("[NavMeshKeeperComponent] failed to read meta '%s': %s",
                            path.string().c_str(), e.what());
            }
        }
        it.increment(ec);
    }

    return {};
}

TcMaterial get_or_create_navmesh_debug_material(TcMaterial& material) {
    if (material.is_valid()) {
        return material;
    }

    material = TcMaterial::create("navmesh_debug_material");
    if (!material.is_valid()) {
        tc_log_error("[NavMesh] Failed to create debug material");
        return material;
    }

    tc_render_state state = tc_render_state_opaque();
    state.depth_test = 1;
    state.depth_write = 0;
    state.cull = 0;
    state.blend = 0;

    tc_material_phase* phase = add_builtin_slang_debug_phase(
        material,
        NAVMESH_DEBUG_SHADER_UUID,
        "navmesh_debug_shader",
        NAVMESH_DEBUG_PHASE,
        0,
        state
    );

    if (!phase) {
        tc_log_error("[NavMesh] Failed to add phase to debug material");
    }

    return material;
}

std::array<float, 4> navmesh_poly_color(int poly_index) {
    float hue = std::fmod((poly_index + 1) * 0.618033988749895f, 1.0f);
    float saturation = 0.5f;
    float value = 1.0f;

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
}

struct NavMeshDebugVertex {
    float pos[3];
    float color[4];
};

void push_detour_vertex(std::vector<NavMeshDebugVertex>& vertices,
                        const float* rc_pos,
                        const std::array<float, 4>& color) {
    vertices.push_back({{
        rc_pos[0],
        rc_pos[2],
        rc_pos[1],
    }, {
        color[0], color[1], color[2], color[3],
    }});
}

const float* detour_detail_vertex(const dtMeshTile* tile,
                                  const dtPoly* poly,
                                  const dtPolyDetail* detail,
                                  unsigned char tri_vertex) {
    if (tri_vertex < poly->vertCount) {
        return &tile->verts[poly->verts[tri_vertex] * 3];
    }
    return &tile->detailVerts[(detail->vertBase + tri_vertex - poly->vertCount) * 3];
}

void append_detour_tile_debug_mesh(const dtMeshTile* tile,
                                   std::vector<NavMeshDebugVertex>& vertices,
                                   std::vector<uint32_t>& indices,
                                   int& poly_offset) {
    if (!tile || !tile->header || !tile->polys || !tile->verts) {
        return;
    }

    const dtMeshHeader* header = tile->header;
    for (int p = 0; p < header->polyCount; ++p) {
        const dtPoly* poly = &tile->polys[p];
        if (poly->getType() != DT_POLYTYPE_GROUND || poly->vertCount < 3) {
            continue;
        }

        const auto color = navmesh_poly_color(poly_offset++);
        if (tile->detailMeshes && tile->detailTris && header->detailTriCount > 0) {
            const dtPolyDetail* detail = &tile->detailMeshes[p];
            for (unsigned int t = 0; t < detail->triCount; ++t) {
                const unsigned char* tri = &tile->detailTris[(detail->triBase + t) * 4];
                const uint32_t base = static_cast<uint32_t>(vertices.size());
                push_detour_vertex(vertices, detour_detail_vertex(tile, poly, detail, tri[0]), color);
                push_detour_vertex(vertices, detour_detail_vertex(tile, poly, detail, tri[1]), color);
                push_detour_vertex(vertices, detour_detail_vertex(tile, poly, detail, tri[2]), color);
                indices.push_back(base);
                indices.push_back(base + 1);
                indices.push_back(base + 2);
            }
            continue;
        }

        const uint32_t base = static_cast<uint32_t>(vertices.size());
        for (unsigned char i = 0; i < poly->vertCount; ++i) {
            push_detour_vertex(vertices, &tile->verts[poly->verts[i] * 3], color);
        }
        for (unsigned char i = 2; i < poly->vertCount; ++i) {
            indices.push_back(base);
            indices.push_back(base + i - 1);
            indices.push_back(base + i);
        }
    }
}

TcMesh build_detour_debug_mesh(const std::vector<std::vector<unsigned char>>& blobs) {
    std::vector<NavMeshDebugVertex> vertices;
    std::vector<uint32_t> indices;
    int poly_offset = 0;

    for (const std::vector<unsigned char>& source_blob : blobs) {
        std::vector<unsigned char> blob = source_blob;
        if (blob.empty()) {
            continue;
        }

        std::unique_ptr<dtNavMesh, decltype(&dtFreeNavMesh)> navmesh(dtAllocNavMesh(), dtFreeNavMesh);
        if (!navmesh) {
            continue;
        }
        if (!dtStatusSucceed(navmesh->init(blob.data(), static_cast<int>(blob.size()), 0))) {
            continue;
        }

        const dtNavMesh* navmesh_view = navmesh.get();
        append_detour_tile_debug_mesh(navmesh_view->getTile(0), vertices, indices, poly_offset);
    }

    if (vertices.empty() || indices.empty()) {
        return {};
    }

    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 1);

    char uuid[40];
    tc_mesh_compute_uuid(vertices.data(), vertices.size() * sizeof(NavMeshDebugVertex),
                         indices.data(), indices.size(), uuid);

    tc_mesh_handle h = tc_mesh_get_or_create(uuid);
    tc_mesh* mesh = tc_mesh_get(h);
    if (!mesh) {
        return {};
    }
    if (mesh->vertex_count == 0) {
        tc_mesh_set_data(mesh,
            vertices.data(), vertices.size(), &layout,
            indices.data(), indices.size(),
            "navmesh_keeper_debug_mesh");
    }

    tc_log_info("[NavMeshKeeperComponent] Detour debug mesh: %zu verts, %zu tris",
                vertices.size(), indices.size() / 3);
    return TcMesh(h);
}

TcMesh build_detour_debug_mesh(const std::filesystem::path& asset_path) {
    std::vector<std::vector<unsigned char>> blobs;
    if (!load_detour_tile_blobs(asset_path, blobs)) {
        return {};
    }
    return build_detour_debug_mesh(blobs);
}

TcMesh build_detour_debug_mesh(const TcNavMesh& navmesh) {
    std::vector<std::vector<unsigned char>> blobs;
    if (!load_detour_tile_blobs_from_navmesh(navmesh, blobs)) {
        return {};
    }
    return build_detour_debug_mesh(blobs);
}

bool load_detour_tile_blobs(const std::filesystem::path& asset_path,
                            std::vector<std::vector<unsigned char>>& blobs) {
    blobs.clear();

    nos::trent data = nos::json::parse_file(asset_path.string());
    if (!data.is_dict() || !data.contains("format") ||
        !data["format"].is_string() || data["format"].as_string() != "termin.detour_navmesh" ||
        !data.contains("tiles") || !data["tiles"].is_list()) {
        return false;
    }

    for (const nos::trent& tile_data : data["tiles"].as_list()) {
        if (!tile_data.is_dict() ||
            !tile_data.contains("data_encoding") ||
            !tile_data["data_encoding"].is_string() ||
            tile_data["data_encoding"].as_string() != "base64" ||
            !tile_data.contains("data") ||
            !tile_data["data"].is_string()) {
            continue;
        }

        std::vector<unsigned char> blob = base64_decode(tile_data["data"].as_string());
        if (!blob.empty()) {
            blobs.push_back(std::move(blob));
        }
    }

    return !blobs.empty();
}

bool load_detour_tile_blobs_from_navmesh(const TcNavMesh& navmesh,
                                         std::vector<std::vector<unsigned char>>& blobs) {
    blobs.clear();
    if (!navmesh.is_valid()) {
        return false;
    }
    if (!navmesh.ensure_loaded()) {
        tc_log_warn("[NavMesh] failed to ensure navmesh loaded uuid=%s", navmesh.uuid());
        return false;
    }

    const tc_navmesh* raw = navmesh.get();
    if (!raw) {
        return false;
    }
    blobs.reserve(raw->tile_count);
    for (size_t i = 0; i < raw->tile_count; ++i) {
        const tc_navmesh_tile& tile = raw->tiles[i];
        if (tile.data && tile.data_size > 0) {
            blobs.emplace_back(tile.data, tile.data + tile.data_size);
        }
    }
    if (blobs.empty()) {
        tc_log_warn("[NavMesh] navmesh has no Detour tile blobs uuid=%s", navmesh.uuid());
        return false;
    }
    return true;
}

std::array<float, 3> termin_to_recast(const std::array<float, 3>& p) {
    return {p[0], p[2], p[1]};
}

std::array<float, 3> recast_to_termin(const float p[3]) {
    return {p[0], p[2], p[1]};
}

} // namespace termin
