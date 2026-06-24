#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cmath>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

#include <termin/render/mesh_renderer.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <tgfx/tgfx_material_handle.hpp>

extern "C" {
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_texture_registry.h>
}

namespace {

constexpr const char* kShaderUuid = "runtime-loader-test-shader";
constexpr const char* kMaterialUuid = "runtime-loader-test-material";

std::filesystem::path make_package_root() {
    std::filesystem::path root = std::filesystem::temp_directory_path()
        / "termin-runtime-package-loader-test";
    std::filesystem::remove_all(root);
    std::filesystem::create_directories(root / "shaders");
    std::filesystem::create_directories(root / "materials");
    return root;
}

void write_text(const std::filesystem::path& path, const std::string& text) {
    std::ofstream out(path, std::ios::binary);
    REQUIRE(static_cast<bool>(out));
    out << text;
    REQUIRE(static_cast<bool>(out));
}

std::string shader_spec() {
    std::ostringstream out;
    out
        << "{\n"
        << "  \"uuid\": \"" << kShaderUuid << "\",\n"
        << "  \"name\": \"RuntimeLoaderTestShader\",\n"
        << "  \"fragment_source_path\": \"shaders/test.frag\"\n"
        << "}\n";
    return out.str();
}

std::string material_spec() {
    std::ostringstream out;
    out
        << "{\n"
        << "  \"uuid\": \"" << kMaterialUuid << "\",\n"
        << "  \"name\": \"RuntimeLoaderTestMaterial\",\n"
        << "  \"phases\": [\n"
        << "    {\"shader\": \"" << kShaderUuid << "\", \"mark\": \"opaque\", \"priority\": 0}\n"
        << "  ],\n"
        << "  \"uniforms\": {\n"
        << "    \"u_color\": [0.25, 0.5, 0.75, 1.0],\n"
        << "    \"u_roughness\": 0.42,\n"
        << "    \"u_emissive\": [0.1, 0.2, 0.3],\n"
        << "    \"u_enabled\": true\n"
        << "  },\n"
        << "  \"textures\": {\n"
        << "    \"u_albedo_texture\": {\"kind\": \"builtin\", \"name\": \"white\"},\n"
        << "    \"u_normal_texture\": {\"kind\": \"builtin\", \"name\": \"normal\"}\n"
        << "  }\n"
        << "}\n";
    return out.str();
}

std::string manifest() {
    return R"({
  "version": 1,
  "shader_artifact_root": ".",
  "resources": [
    {"type": "shader", "uuid": "runtime-loader-test-shader", "path": "shaders/test.shader.json"},
    {"type": "material", "uuid": "runtime-loader-test-material", "path": "materials/test.tmat.json"}
  ],
  "scene": "scene.json"
}
)";
}

std::string scene_json() {
    return R"({
  "uuid": "runtime-loader-test-scene",
  "entities": [
    {
      "uuid": "runtime-loader-test-entity",
      "name": "RuntimeLoaderTestEntity",
      "visible": true,
      "enabled": true,
      "pose": {
        "position": [0.0, 0.0, 0.0],
        "rotation": [0.0, 0.0, 0.0, 1.0]
      },
      "scale": [1.0, 1.0, 1.0],
      "components": [
        {
          "type": "MeshRenderer",
          "data": {
            "enabled": true,
            "material": {
              "uuid": "runtime-loader-test-material",
              "name": "RuntimeLoaderTestMaterial",
              "type": "uuid"
            },
            "cast_shadow": true,
            "mesh_offset_enabled": false,
            "mesh_offset_position": [0.0, 0.0, 0.0],
            "mesh_offset_euler": [0.0, 0.0, 0.0],
            "mesh_offset_scale": [1.0, 1.0, 1.0],
            "_override_material": false
          }
        }
      ]
    }
  ]
}
)";
}

void write_test_package(const std::filesystem::path& root) {
    write_text(root / "manifest.json", manifest());
    write_text(root / "scene.json", scene_json());
    write_text(root / "shaders" / "test.shader.json", shader_spec());
    write_text(root / "shaders" / "test.frag", R"(
#version 330 core
uniform sampler2D u_albedo_texture;
uniform sampler2D u_normal_texture;
layout(std140) uniform Material {
    vec4 u_color;
    float u_roughness;
    vec3 u_emissive;
    int u_enabled;
};
out vec4 FragColor;
void main() {
    FragColor = u_color;
}
)");
    write_text(root / "materials" / "test.tmat.json", material_spec());
}

tc_uniform_value* require_uniform(tc_material_phase* phase, const char* name, tc_uniform_type type) {
    REQUIRE(phase != nullptr);
    tc_uniform_value* value = tc_material_phase_find_uniform(phase, name);
    REQUIRE(value != nullptr);
    CHECK_EQ(value->type, static_cast<unsigned char>(type));
    return value;
}

tc_material_texture* require_texture(tc_material_phase* phase, const char* name) {
    REQUIRE(phase != nullptr);
    tc_material_texture* texture = tc_material_phase_find_texture(phase, name);
    REQUIRE(texture != nullptr);
    CHECK(tc_texture_is_valid(texture->texture));
    return texture;
}

} // namespace

TEST_CASE("RuntimePackageLoader applies material uniforms and builtin textures") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    termin::runtime::RuntimePackageLoader loader;
    termin::runtime::RuntimePackageLoadResult result = loader.load(root.string());
    REQUIRE(result.ok);
    REQUIRE(result.scene.valid());

    termin::TcMaterial material = termin::TcMaterial::from_uuid(kMaterialUuid);
    REQUIRE(material.is_valid());
    tc_material_phase* phase = material.default_phase();
    REQUIRE(phase != nullptr);

    tc_uniform_value* color = require_uniform(phase, "u_color", TC_UNIFORM_VEC4);
    CHECK(std::fabs(color->data.v4[0] - 0.25f) < 0.0001f);
    CHECK(std::fabs(color->data.v4[1] - 0.5f) < 0.0001f);
    CHECK(std::fabs(color->data.v4[2] - 0.75f) < 0.0001f);
    CHECK(std::fabs(color->data.v4[3] - 1.0f) < 0.0001f);

    tc_uniform_value* roughness = require_uniform(phase, "u_roughness", TC_UNIFORM_FLOAT);
    CHECK(std::fabs(roughness->data.f - 0.42f) < 0.0001f);

    tc_uniform_value* emissive = require_uniform(phase, "u_emissive", TC_UNIFORM_VEC3);
    CHECK(std::fabs(emissive->data.v3[0] - 0.1f) < 0.0001f);
    CHECK(std::fabs(emissive->data.v3[1] - 0.2f) < 0.0001f);
    CHECK(std::fabs(emissive->data.v3[2] - 0.3f) < 0.0001f);

    tc_uniform_value* enabled = require_uniform(phase, "u_enabled", TC_UNIFORM_INT);
    CHECK_EQ(enabled->data.i, 1);

    require_texture(phase, "u_albedo_texture");
    require_texture(phase, "u_normal_texture");
}
