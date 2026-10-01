#include <termin/glb/native_backend.h>

#include <tgfx/resources/tc_mesh_registry.h>

#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <string>
#include <vector>

namespace {
    struct MathFixture {
        std::array<float, 9> positions{0, 0, 0, 1, 0, 0, 0, 1, 0};
        std::array<float, 3> normal{1, 0, -1};
        std::array<float, 4> tangent{4, 0, 0, -1};
        std::array<float, 6> uvs{0, 0, 1, 0, 0, 1};
        bool normals = true;
        bool tangents = false;
        bool skinned = false;
        bool texcoords = true;
    };

    void append_u32(std::vector<unsigned char>& output, uint32_t value) {
        for (unsigned shift = 0; shift < 32; shift += 8)
            output.push_back(static_cast<unsigned char>(value >> shift));
    }

    std::vector<unsigned char> float_bytes(const float* values, size_t count) {
        std::vector<unsigned char> bytes;
        for (size_t i = 0; i < count; ++i) {
            uint32_t bits;
            std::memcpy(&bits, values + i, sizeof(bits));
            append_u32(bytes, bits);
        }
        return bytes;
    }

    bool write_math_fixture(const std::filesystem::path& path, const MathFixture& fixture) {
        std::vector<unsigned char> binary;
        std::string views;
        std::string accessors;
        std::string attributes;
        size_t accessor_index = 0;
        const auto append = [&](const char* semantic, const std::vector<unsigned char>& bytes,
                                 int component_type, const char* type) {
            while (binary.size() % 4)
                binary.push_back(0);
            const std::string index = std::to_string(accessor_index++);
            if (!views.empty()) {
                views += ',';
                accessors += ',';
                attributes += ',';
            }
            views += "{\"buffer\":0,\"byteOffset\":" + std::to_string(binary.size()) +
                     ",\"byteLength\":" + std::to_string(bytes.size()) + '}';
            accessors += "{\"bufferView\":" + index + ",\"componentType\":" + std::to_string(component_type) +
                         ",\"count\":3,\"type\":\"" + type + "\"}";
            attributes += '"' + std::string(semantic) + "\":" + index;
            binary.insert(binary.end(), bytes.begin(), bytes.end());
        };
        append("POSITION", float_bytes(fixture.positions.data(), fixture.positions.size()), 5126, "VEC3");
        if (fixture.normals) {
            std::array<float, 9> values;
            for (size_t i = 0; i < values.size(); ++i)
                values[i] = fixture.normal[i % 3];
            append("NORMAL", float_bytes(values.data(), values.size()), 5126, "VEC3");
        }
        if (fixture.texcoords)
            append("TEXCOORD_0", float_bytes(fixture.uvs.data(), fixture.uvs.size()), 5126, "VEC2");
        if (fixture.tangents) {
            std::array<float, 12> values;
            for (size_t i = 0; i < values.size(); ++i)
                values[i] = fixture.tangent[i % 4];
            append("TANGENT", float_bytes(values.data(), values.size()), 5126, "VEC4");
        }
        if (fixture.skinned) {
            append("JOINTS_0", std::vector<unsigned char>(24, 0), 5123, "VEC4");
            const float weights[] = {1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0};
            append("WEIGHTS_0", float_bytes(weights, 12), 5126, "VEC4");
        }
        std::string json = "{\"asset\":{\"version\":\"2.0\"},\"buffers\":[{\"byteLength\":" +
                           std::to_string(binary.size()) + "}],\"bufferViews\":[" + views +
                           "],\"accessors\":[" + accessors + "],\"meshes\":[{\"name\":\"MathFixture\","
                           "\"primitives\":[{\"attributes\":{" + attributes + "}}]}]}";
        while (json.size() % 4)
            json += ' ';
        while (binary.size() % 4)
            binary.push_back(0);
        std::vector<unsigned char> glb;
        append_u32(glb, 0x46546c67);
        append_u32(glb, 2);
        append_u32(glb, static_cast<uint32_t>(28 + json.size() + binary.size()));
        append_u32(glb, static_cast<uint32_t>(json.size()));
        append_u32(glb, 0x4e4f534a);
        glb.insert(glb.end(), json.begin(), json.end());
        append_u32(glb, static_cast<uint32_t>(binary.size()));
        append_u32(glb, 0x004e4942);
        glb.insert(glb.end(), binary.begin(), binary.end());
        std::ofstream stream(path, std::ios::binary);
        stream.write(reinterpret_cast<const char*>(glb.data()), static_cast<std::streamsize>(glb.size()));
        if (!stream) {
            std::fprintf(stderr, "Failed to write native GLB math fixture %s\n", path.string().c_str());
            return false;
        }
        return true;
    }

    bool test_checked_mesh_math() {
        const auto serial = std::chrono::steady_clock::now().time_since_epoch().count();
        const auto root = std::filesystem::temp_directory_path() / ("termin-glb-math-" + std::to_string(serial));
        std::error_code ec;
        std::filesystem::create_directories(root, ec);
        if (ec) {
            std::fprintf(stderr, "Failed to create native GLB math fixture directory: %s\n", ec.message().c_str());
            return false;
        }
        const auto sentinel_handle = tc_mesh_find("native-box");
        const tc_mesh* sentinel = tc_mesh_get(sentinel_handle);
        const uint32_t version = sentinel->header.version;
        const std::string name = sentinel->header.name;
        std::array<unsigned char, sizeof(tc_vertex_layout)> layout_bytes{};
        std::memcpy(layout_bytes.data(), &sentinel->layout, layout_bytes.size());
        const size_t vertex_count = sentinel->vertex_count;
        const size_t index_count = sentinel->index_count;
        const size_t submesh_count = sentinel->submesh_count;
        const auto* vertex_bytes = static_cast<const unsigned char*>(sentinel->vertices);
        const std::vector<unsigned char> vertices(vertex_bytes, vertex_bytes + vertex_count * sentinel->layout.stride);
        const std::vector<uint32_t> indices(sentinel->indices, sentinel->indices + index_count);
        const auto* submesh_bytes = reinterpret_cast<const unsigned char*>(sentinel->submeshes);
        const std::vector<unsigned char> submeshes(submesh_bytes, submesh_bytes + submesh_count * sizeof(tc_submesh));
        const auto rejected = [&](const char* label, const MathFixture& fixture, const char* semantic) {
            const auto path = root / (std::string(label) + ".glb");
            if (!write_math_fixture(path, fixture))
                return false;
            termin_glb_error error{};
            auto* document = termin_glb_document_open(path.string().c_str(), &error);
            if (!document) {
                std::fprintf(stderr, "Native GLB math fixture %s did not reach mesh build: %s\n", label, error.message);
                return false;
            }
            const bool built = termin_glb_document_build_mesh(document, 0, "native-box", "Rejected replacement", false, &error);
            termin_glb_document_close(document);
            sentinel = tc_mesh_get(sentinel_handle);
            const bool unchanged = sentinel && sentinel->header.version == version && name == sentinel->header.name &&
                sentinel->vertex_count == vertex_count && sentinel->index_count == index_count &&
                sentinel->submesh_count == submesh_count &&
                std::memcmp(&sentinel->layout, layout_bytes.data(), layout_bytes.size()) == 0 &&
                std::memcmp(sentinel->vertices, vertices.data(), vertices.size()) == 0 &&
                std::memcmp(sentinel->indices, indices.data(), indices.size() * sizeof(uint32_t)) == 0 &&
                std::memcmp(sentinel->submeshes, submeshes.data(), submeshes.size()) == 0;
            const bool valid = !built && error.code == TERMIN_GLB_ERROR_INVALID_FORMAT && unchanged &&
                std::strstr(error.message, path.string().c_str()) && std::strstr(error.message, "mesh[0]") &&
                std::strstr(error.message, "primitive[0]") && std::strstr(error.message, semantic);
            if (!valid)
                std::fprintf(stderr, "Native GLB rejection %s failed: built=%d unchanged=%d code=%d %s\n",
                             label, built, unchanged, error.code, error.message);
            return valid;
        };
        const auto accepted = [&](const char* label, const MathFixture& fixture, bool generated) {
            const auto path = root / (std::string(label) + ".glb");
            if (!write_math_fixture(path, fixture))
                return false;
            termin_glb_error error{};
            auto* document = termin_glb_document_open(path.string().c_str(), &error);
            if (!document)
                return false;
            const std::string uuid = std::string("native-math-") + label;
            const bool built = termin_glb_document_build_mesh(document, 0, uuid.c_str(), label, false, &error);
            termin_glb_document_close(document);
            const auto handle = tc_mesh_find(uuid.c_str());
            const auto* mesh = tc_mesh_get(handle);
            bool valid = built && mesh && mesh->vertex_count == 3 && mesh->layout.stride == (fixture.skinned ? 80u : 48u);
            for (size_t i = 0; valid && i < mesh->vertex_count; ++i) {
                const auto* vertex = reinterpret_cast<const float*>(
                    static_cast<const unsigned char*>(mesh->vertices) + i * mesh->layout.stride);
                float normal_length = 0;
                float tangent_length = 0;
                float dot = 0;
                for (size_t c = 0; c < 3; ++c) {
                    valid = valid && std::isfinite(vertex[3 + c]) && std::isfinite(vertex[8 + c]);
                    normal_length += vertex[3 + c] * vertex[3 + c];
                    tangent_length += vertex[8 + c] * vertex[8 + c];
                    dot += vertex[3 + c] * vertex[8 + c];
                }
                valid = valid && std::fabs(normal_length - 1) < 1e-6f && std::fabs(tangent_length - 1) < 1e-6f;
                const float diagonal = std::sqrt(0.5f);
                const std::array<float, 3> expected_normal = fixture.normal[0] == 0 ?
                    std::array<float, 3>{0, 0, 1} : std::array<float, 3>{diagonal, 0, -diagonal};
                for (size_t c = 0; c < 3; ++c)
                    valid = valid && std::fabs(vertex[3 + c] - expected_normal[c]) < 1e-6f;
                if (generated) {
                    valid = valid && std::fabs(dot) < 1e-6f && vertex[11] == -1 &&
                        std::fabs(vertex[8] - diagonal) < 1e-6f && std::fabs(vertex[9]) < 1e-6f &&
                        std::fabs(vertex[10] - diagonal) < 1e-6f;
                } else {
                    valid = valid && vertex[11] == fixture.tangent[3] && std::fabs(vertex[8] - 1) < 1e-6f;
                }
            }
            if (!tc_mesh_handle_is_invalid(handle))
                tc_mesh_destroy(handle);
            if (!valid)
                std::fprintf(stderr, "Native GLB accepted math fixture %s failed: %s\n", label, error.message);
            return valid;
        };
        bool valid = true;
        MathFixture fixture;
        valid = accepted("generated-nonunit-normal", fixture, true) && valid;
        fixture.tangents = true;
        valid = accepted("authored-nonunit-normal-tangent", fixture, false) && valid;
        fixture.normal = {0, 0, 1};
        valid = accepted("authored-unit-normal", fixture, false) && valid;
        fixture.skinned = true;
        valid = accepted("authored-skinned", fixture, false) && valid;
        fixture.normal = {1e38f, 0, -1e38f};
        fixture.tangent = {1e38f, 0, 0, -1};
        valid = accepted("authored-large-finite", fixture, false) && valid;
        const float nan = std::numeric_limits<float>::quiet_NaN();
        const float inf = std::numeric_limits<float>::infinity();
        for (const bool skinned : {false, true}) {
            for (const float invalid : {0.0f, nan, inf}) {
                fixture = MathFixture{};
                fixture.skinned = skinned;
                fixture.tangents = true;
                fixture.normal = {invalid, 0, 0};
                valid = rejected("invalid-normal", fixture, "NORMAL") && valid;
                fixture.normal = {0, 0, 1};
                fixture.tangent = {invalid, 0, 0, 1};
                valid = rejected("invalid-tangent", fixture, "TANGENT") && valid;
                fixture.tangent = {1, 0, 0, invalid};
                valid = rejected("invalid-handedness", fixture, "TANGENT") && valid;
            }
        }
        fixture = MathFixture{};
        fixture.normals = false;
        fixture.positions = {0, 0, 0, 1, 0, 0, 2, 0, 0};
        valid = rejected("degenerate-generated-normal", fixture, "generated NORMAL") && valid;
        fixture = MathFixture{};
        fixture.uvs.fill(0);
        valid = rejected("degenerate-generated-tangent", fixture, "generated TANGENT") && valid;
        fixture = MathFixture{};
        fixture.positions[0] = inf;
        valid = rejected("nonfinite-position", fixture, "POSITION") && valid;
        fixture = MathFixture{};
        fixture.uvs[0] = nan;
        valid = rejected("nonfinite-uv", fixture, "TEXCOORD_0") && valid;
        std::filesystem::remove_all(root, ec);
        if (ec) {
            std::fprintf(stderr, "Failed to remove native GLB math fixtures: %s\n", ec.message().c_str());
            valid = false;
        }
        return valid;
    }
} // namespace

int main() {
    if (std::strcmp(termin_glb_backend_name(), "cgltf") != 0)
        return 1;
    if (std::strcmp(termin_glb_cgltf_version(), TERMIN_GLB_CGLTF_VERSION) != 0)
        return 2;
    if (std::strcmp(termin_glb_cgltf_revision(), TERMIN_GLB_CGLTF_REVISION) != 0)
        return 3;
    if (std::strcmp(termin_glb_error_code_name(TERMIN_GLB_ERROR_UNSUPPORTED), "unsupported") != 0)
        return 4;

    termin_glb_error error{TERMIN_GLB_ERROR_INTERNAL, "failure"};
    termin_glb_error_clear(&error);
    if (error.code != TERMIN_GLB_ERROR_NONE || error.message[0] != '\0')
        return 5;

    const std::string fixture_dir = TERMIN_GLB_TEST_FIXTURE_DIR;
    const std::string box_path = fixture_dir + "/Box.glb";
    termin_glb_document* document = termin_glb_document_open(box_path.c_str(), &error);
    if (!document)
        return 6;
    if (termin_glb_document_mesh_count(document) != 1)
        return 7;

    termin_glb_mesh_info info = {};
    if (!termin_glb_document_mesh_info(document, 0, &info, &error))
        return 8;
    if (std::strcmp(info.name, "Mesh") != 0 || info.primitive_count != 1 || info.vertex_count != 24 ||
        info.index_count != 36 || info.skinned)
        return 9;
    if (termin_glb_document_material_count(document) != 1 || termin_glb_document_image_count(document) != 0 ||
        termin_glb_document_texture_count(document) != 0)
        return 16;
    termin_glb_material_info material = {};
    if (!termin_glb_document_material_info(document, 0, &material, &error) ||
        std::strcmp(material.name, "Red") != 0 || material.base_color_texture.present)
        return 17;
    if (termin_glb_document_node_count(document) != 2 || termin_glb_document_skin_count(document) != 0 ||
        termin_glb_document_animation_count(document) != 0)
        return 18;
    termin_glb_node_info node = {};
    if (!termin_glb_document_node_info(document, 0, &node, &error) || !node.default_scene_root)
        return 19;

    tc_mesh_init();
    if (!termin_glb_document_build_static_mesh(document, 0, "native-box", "Native Box", true, &error))
        return 10;
    tc_mesh_handle handle = tc_mesh_find("native-box");
    tc_mesh* mesh = tc_mesh_get(handle);
    if (!mesh || mesh->vertex_count != 24 || mesh->index_count != 36 || mesh->submesh_count != 1)
        return 11;
    if (mesh->layout.stride != 24 || mesh->submeshes[0].index_count != 36 ||
        std::strcmp(mesh->submeshes[0].name, "Mesh/Red") != 0)
        return 12;
    for (size_t i = 0; i < mesh->index_count; ++i) {
        if (mesh->indices[i] >= mesh->vertex_count)
            return 13;
    }
    termin_glb_document_close(document);

    const std::string gltf_path = fixture_dir + "/TriangleWithoutIndices.gltf";
    document = termin_glb_document_open(gltf_path.c_str(), &error);
    if (document || error.code != TERMIN_GLB_ERROR_UNSUPPORTED ||
        std::strstr(error.message, gltf_path.c_str()) == nullptr)
        return 14;

    for (int i = 0; i < 64; ++i) {
        document = termin_glb_document_open(box_path.c_str(), &error);
        if (!document)
            return 15;
        termin_glb_document_close(document);
    }
    if (!test_checked_mesh_math())
        return 20;
    tc_mesh_shutdown();
    return 0;
}
