#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include <termin/entity/entity.hpp>
#include <termin/image/image_decode.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/tc_scene_render_accessors.hpp>
#include <termin/render/tc_pipeline_template.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_shader_program_handle.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <core/tc_light_capability.h>
#include <core/tc_scene.h>
#include <core/tc_scene_render_mount.h>
#include <render/tc_pipeline_template_registry.h>
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_texture_registry.h>
}

namespace {

constexpr const char* kProgramUuid = "runtime-loader-test-program";
constexpr const char* kShaderUuid = "shader-phase-12beb2a809af29f7";
constexpr const char* kMaterialUuid = "runtime-loader-test-material";
constexpr const char* kMeshUuid = "runtime-loader-test-mesh";
constexpr const char* kMeshName = "RuntimeLoaderTestMesh";
constexpr const char* kTextureUuid = "runtime-loader-test-texture";
constexpr const char* kTextureName = "RuntimeLoaderTestTexture";

std::filesystem::path make_package_root() {
    std::filesystem::path root = std::filesystem::temp_directory_path()
        / "termin-runtime-package-loader-test";
    std::filesystem::remove_all(root);
    std::filesystem::create_directories(root / "shaders");
    std::filesystem::create_directories(root / "materials");
    std::filesystem::create_directories(root / "meshes");
    std::filesystem::create_directories(root / "textures");
    std::filesystem::create_directories(root / "pipelines");
    return root;
}

void write_binary(const std::filesystem::path& path, const std::vector<std::uint8_t>& bytes) {
    std::ofstream out(path, std::ios::binary);
    REQUIRE(static_cast<bool>(out));
    out.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    REQUIRE(static_cast<bool>(out));
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
        << "  \"language\": \"glsl\",\n"
        << "  \"fragment_source_path\": \"shaders/test.frag\",\n"
        << "  \"features\": 1\n"
        << "}\n";
    return out.str();
}

std::string shader_program_spec() {
    std::ostringstream out;
    out
        << "{\n"
        << "  \"schema_version\": 1,\n"
        << "  \"uuid\": \"" << kProgramUuid << "\",\n"
        << "  \"name\": \"RuntimeLoaderTestProgram\",\n"
        << "  \"source_path\": \"packaged-test\",\n"
        << "  \"language\": \"glsl\",\n"
        << "  \"features\": 1,\n"
        << "  \"properties\": [\n"
        << "    {\"name\": \"u_color\", \"property_type\": \"Color\", "
           "\"default\": [1.0, 0.5, 0.25, 1.0]}\n"
        << "  ],\n"
        << "  \"phases\": [\n"
        << "    {\"phase_mark\": \"opaque\", \"priority\": 0, \"shader\": \""
        << kShaderUuid << "\", \"state\": {\"polygon_mode\": 0, \"cull\": true, "
           "\"depth_test\": true, \"depth_write\": true, \"blend\": false, "
           "\"blend_src\": 2, \"blend_dst\": 3, \"depth_func\": 0}}\n"
        << "  ]\n"
        << "}\n";
    return out.str();
}

std::string mesh_spec() {
    return R"({
  "uuid": "runtime-loader-test-mesh",
  "name": "RuntimeLoaderTestMesh",
  "draw_mode": "triangles",
  "layout": [
    {"name": "position", "type": "float32", "components": 3, "location": 0}
  ],
  "vertices": [
    0.0, 0.0, 0.0,
    1.0, 0.0, 0.0,
    0.0, 1.0, 0.0
  ],
  "indices": [0, 1, 2]
}
)";
}

std::string material_spec() {
    std::ostringstream out;
    out
        << "{\n"
        << "  \"uuid\": \"" << kMaterialUuid << "\",\n"
        << "  \"name\": \"RuntimeLoaderTestMaterial\",\n"
        << "  \"shader_program\": \"" << kProgramUuid << "\",\n"
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
  "resources": [
    {"type": "shader", "uuid": "shader-phase-12beb2a809af29f7", "path": "shaders/test.shader.json"},
    {"type": "shader_program", "uuid": "runtime-loader-test-program", "path": "shaders/test.shader-program.json"},
    {"type": "material", "uuid": "runtime-loader-test-material", "path": "materials/test.tmat.json"},
    {"type": "mesh", "uuid": "runtime-loader-test-mesh", "path": "meshes/test.tmesh.json"}
  ],
  "scene": "scene.json"
}
)";
}

std::string replace_once(std::string text, const std::string& needle, const std::string& replacement) {
    const size_t offset = text.find(needle);
    REQUIRE(offset != std::string::npos);
    text.replace(offset, needle.size(), replacement);
    return text;
}

std::string texture_spec(const std::string& source_path = "textures/albedo.png") {
    std::ostringstream out;
    out
        << "{\n"
        << "  \"uuid\": \"" << kTextureUuid << "\",\n"
        << "  \"name\": \"" << kTextureName << "\",\n"
        << "  \"source_path\": \"" << source_path << "\",\n"
        << "  \"import_settings\": {\"flip_x\": true, \"flip_y\": false, \"transpose\": true}\n"
        << "}\n";
    return out.str();
}

std::string material_spec_with_asset_texture() {
    return replace_once(
        material_spec(),
        "{\"kind\": \"builtin\", \"name\": \"white\"}",
        std::string("{\"kind\": \"asset\", \"uuid\": \"") + kTextureUuid + "\"}"
    );
}

std::string manifest_with_packaged_texture() {
    return R"({
  "version": 1,
  "resources": [
    {"type": "material", "uuid": "runtime-loader-test-material", "path": "materials/test.tmat.json"},
    {"type": "texture", "uuid": "runtime-loader-test-texture", "path": "textures/test.texture.json"},
    {"type": "mesh", "uuid": "runtime-loader-test-mesh", "path": "meshes/test.tmesh.json"},
    {"type": "shader", "uuid": "shader-phase-12beb2a809af29f7", "path": "shaders/test.shader.json"},
    {"type": "shader_program", "uuid": "runtime-loader-test-program", "path": "shaders/test.shader-program.json"}
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
          "type": "MeshComponent",
          "data": {
            "enabled": true,
            "mesh": {
              "uuid": "runtime-loader-test-mesh",
              "name": "RuntimeLoaderTestMesh",
              "type": "uuid"
            },
            "mesh_offset_enabled": false,
            "mesh_offset_position": [0.0, 0.0, 0.0],
            "mesh_offset_euler": [0.0, 0.0, 0.0],
            "mesh_offset_scale": [1.0, 1.0, 1.0]
          }
        },
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
    },
    {
      "uuid": "runtime-loader-test-light",
      "name": "RuntimeLoaderTestLight",
      "visible": true,
      "enabled": true,
      "pose": {
        "position": [0.0, 2.0, 3.0],
        "rotation": [0.0, 0.0, 0.0, 1.0]
      },
      "scale": [1.0, 1.0, 1.0],
      "components": [
        {
          "type": "LightComponent",
          "data": {
            "light_type": "directional",
            "color": [0.8, 0.9, 1.0],
            "intensity": 3.5,
            "shadows_enabled": true,
            "shadows_bias": 0.002,
            "shadows_normal_bias": 0.1,
            "shadows_map_resolution": 1024,
            "cascade_count": 2,
            "max_distance": 50.0,
            "split_lambda": 0.4,
            "cascade_blend": true
          }
        }
      ]
    }
  ],
  "extensions": {
    "render_state": {
      "background_color": [0.05, 0.06, 0.07, 1.0],
      "lighting": {
        "ambient_color": [0.7, 0.8, 0.9],
        "ambient_intensity": 0.33,
        "shadow_settings": {
          "method": 1,
          "softness": 0.75,
          "bias": 0.003
        }
      }
    }
  }
}
)";
}

void write_test_package(const std::filesystem::path& root) {
    write_text(root / "manifest.json", manifest());
    write_text(root / "scene.json", scene_json());
    write_text(root / "shaders" / "test.shader.json", shader_spec());
    write_text(root / "shaders" / "test.shader-program.json", shader_program_spec());
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
    write_text(root / "meshes" / "test.tmesh.json", mesh_spec());
}

void write_test_package_with_texture(const std::filesystem::path& root) {
    write_test_package(root);
    write_text(root / "manifest.json", manifest_with_packaged_texture());
    write_text(root / "materials" / "test.tmat.json", material_spec_with_asset_texture());
    write_text(root / "textures" / "test.texture.json", texture_spec());
    const std::vector<std::uint8_t> rgba = {
        0x10, 0x20, 0x30, 0x40,
        0x50, 0x60, 0x70, 0x80,
    };
    write_binary(root / "textures" / "albedo.png", termin::image::encode_png_rgba8(rgba, 2, 1));
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

struct LightProbe {
    size_t count = 0;
    tc_light_data first{};
};

bool collect_test_light(tc_component* c, void* user_data) {
    LightProbe* probe = static_cast<LightProbe*>(user_data);
    const tc_light_capability* cap = tc_light_capability_get(c);
    REQUIRE(cap != nullptr);
    REQUIRE(cap->vtable != nullptr);
    REQUIRE(cap->vtable->get_light_data != nullptr);
    tc_light_data data{};
    REQUIRE(cap->vtable->get_light_data(c, &data));
    if (probe->count == 0) {
        probe->first = data;
    }
    ++probe->count;
    return true;
}

} // namespace

TEST_CASE("RuntimePackageLoader applies material uniforms and builtin textures") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    termin::tgfx2_set_shader_artifact_root("runtime-loader-sentinel");
    termin::runtime::RuntimePackageLoader loader;
    termin::runtime::RuntimePackageLoadResult result = loader.load(root.string());
    REQUIRE(result.ok);
    REQUIRE(result.scene.valid());
    CHECK(result.shader_runtime.artifact_root == root.string());
    CHECK(result.shader_runtime.cache_root == (root / ".shader-cache").string());
    CHECK(std::string(termin::tgfx2_get_shader_artifact_root()) == "runtime-loader-sentinel");
    termin::tgfx2_set_shader_artifact_root("");

    termin::TcMaterial material = termin::TcMaterial::from_uuid(kMaterialUuid);
    REQUIRE(material.is_valid());
    termin::TcShaderProgram program = termin::TcShaderProgram::find(kProgramUuid);
    REQUIRE(program.is_valid());
    CHECK_EQ(std::string(material.shader_program_uuid()), std::string(kProgramUuid));
    CHECK_EQ(material.shader_program_version(), program.version());
    REQUIRE(program.get() != nullptr);
    CHECK_EQ(program.get()->property_count, 1u);
    CHECK_EQ(program.get()->phase_count, 1u);
    tc_shader* program_phase_shader = tc_shader_get(program.get()->phases[0].shader);
    REQUIRE(program_phase_shader != nullptr);
    CHECK_EQ(std::string(program_phase_shader->uuid), std::string(kShaderUuid));
    tc_material_phase* phase = material.default_phase();
    REQUIRE(phase != nullptr);

    termin::TcShader shader = termin::TcShader::from_uuid(kShaderUuid);
    REQUIRE(shader.is_valid());
    CHECK(shader.has_feature(TC_SHADER_FEATURE_LIGHTING_UBO));

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

    tc_scene_handle scene = result.scene.handle();
    CHECK_EQ(tc_scene_count_components_of_type(scene, "LightComponent"), 1);

    tc_component_cap_id light_cap = tc_light_capability_id();
    REQUIRE(light_cap != TC_COMPONENT_CAPABILITY_INVALID_ID);
    CHECK_EQ(tc_scene_capability_count(scene, light_cap), 1);

    LightProbe probe;
    tc_scene_foreach_with_capability(
        scene,
        light_cap,
        collect_test_light,
        &probe,
        TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
    REQUIRE_EQ(probe.count, 1);
    CHECK_EQ(probe.first.type, TC_LIGHT_DIRECTIONAL);
    CHECK(std::fabs(probe.first.color[0] - 0.8) < 0.0001);
    CHECK(std::fabs(probe.first.color[1] - 0.9) < 0.0001);
    CHECK(std::fabs(probe.first.color[2] - 1.0) < 0.0001);
    CHECK(std::fabs(probe.first.intensity - 3.5) < 0.0001);

    tc_scene_lighting* lighting = termin::scene_lighting(result.scene);
    REQUIRE(lighting != nullptr);
    CHECK(std::fabs(lighting->ambient_color[0] - 0.7f) < 0.0001f);
    CHECK(std::fabs(lighting->ambient_color[1] - 0.8f) < 0.0001f);
    CHECK(std::fabs(lighting->ambient_color[2] - 0.9f) < 0.0001f);
    CHECK(std::fabs(lighting->ambient_intensity - 0.33f) < 0.0001f);
}

TEST_CASE("RuntimePackageLoader loads compiled pipeline templates before the scene") {
    const std::filesystem::path root = make_package_root();
    constexpr const char* pipeline_uuid = "runtime-loader-compiled-pipeline";

    const tc_pipeline_template_payload_desc descriptor = {
        TC_PIPELINE_TEMPLATE_DESCRIPTOR_VERSION,
        "Runtime Compiled Pipeline",
        nullptr, 0,
        nullptr, 0,
        nullptr, 0,
        nullptr, 0,
    };
    const tc_pipeline_template_handle source_handle = tc_pipeline_template_create(
        "runtime-loader-compiled-pipeline-source", "source");
    tc_pipeline_template* source = tc_pipeline_template_get(source_handle);
    REQUIRE(source != nullptr);
    REQUIRE(tc_pipeline_template_set_payload(source, &descriptor));
    const size_t payload_size = tc_pipeline_template_serialize(source, nullptr, 0);
    REQUIRE(payload_size > 0);
    std::vector<std::uint8_t> payload(payload_size);
    REQUIRE_EQ(
        tc_pipeline_template_serialize(source, payload.data(), payload.size()),
        payload_size);
    REQUIRE(tc_pipeline_template_remove(source_handle));

    write_binary(root / "pipelines" / "compiled.pipeline-template", payload);
    write_text(root / "manifest.json", R"({
  "version": 1,
  "resources": [
    {"type": "pipeline", "uuid": "runtime-loader-compiled-pipeline", "name": "Runtime Compiled Pipeline", "path": "pipelines/compiled.pipeline-template"}
  ],
  "scene": "scene.json"
}
)");
    write_text(root / "scene.json", R"({
  "uuid": "runtime-loader-pipeline-scene",
  "entities": [],
  "extensions": {
    "render_mount": {
      "pipeline_templates": [
        {"uuid": "runtime-loader-compiled-pipeline"}
      ],
      "viewport_configs": [],
      "render_target_configs": []
    }
  }
}
)");

    termin::runtime::RuntimePackageLoadResult result =
        termin::runtime::load_runtime_package(root.string());
    REQUIRE(result.ok);
    REQUIRE(result.resources != nullptr);
    const tc_pipeline_template_handle loaded = tc_pipeline_template_find(pipeline_uuid);
    REQUIRE(tc_pipeline_template_is_valid(loaded));
    const tc_pipeline_template* loaded_template = tc_pipeline_template_get(loaded);
    REQUIRE(loaded_template != nullptr);
    CHECK_EQ(std::string(loaded_template->header.name), "Runtime Compiled Pipeline");
    CHECK_EQ(tc_scene_pipeline_template_count(result.scene.handle()), 1u);
    CHECK(tc_pipeline_template_handle_eq(
        tc_scene_pipeline_template_at(result.scene.handle(), 0), loaded));
}

TEST_CASE("RuntimePackageLoader requires an explicit supported shader language") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    write_text(
        root / "shaders" / "test.shader.json",
        replace_once(shader_spec(), "  \"language\": \"glsl\",\n", ""));
    termin::runtime::RuntimePackageLoadResult missing =
        termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(missing.ok);
    CHECK(missing.message.find("has no explicit language") != std::string::npos);

    write_text(
        root / "shaders" / "test.shader.json",
        replace_once(shader_spec(), "\"language\": \"glsl\"", "\"language\": \"spirv\""));
    termin::runtime::RuntimePackageLoadResult unsupported =
        termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(unsupported.ok);
    CHECK(unsupported.message.find("unsupported language 'spirv'") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader rejects incompatible shader program schema") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);
    write_text(
        root / "shaders" / "test.shader-program.json",
        replace_once(shader_program_spec(), "\"schema_version\": 1", "\"schema_version\": 99"));

    termin::runtime::RuntimePackageLoadResult result =
        termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(result.ok);
    CHECK(result.message.find("requires schema_version 1") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader fails closed when the entry scene is missing or invalid") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    std::filesystem::remove(root / "scene.json");
    termin::runtime::RuntimePackageLoadResult missing =
        termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(missing.ok);
    CHECK_FALSE(missing.scene.valid());
    CHECK(missing.message.find("failed to open file") != std::string::npos);
    CHECK(missing.message.find("scene.json") != std::string::npos);

    write_text(root / "scene.json", "{ invalid scene json");
    termin::runtime::RuntimePackageLoadResult invalid =
        termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(invalid.ok);
    CHECK_FALSE(invalid.scene.valid());
    CHECK(invalid.message.find("failed to parse runtime entry scene") != std::string::npos);
    CHECK(invalid.message.find("scene.json") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader keeps package meshes alive after scene entity removal") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
    REQUIRE(result.ok);
    REQUIRE(result.scene.valid());
    REQUIRE(result.resources != nullptr);

    tc_mesh_handle loaded = tc_mesh_find_by_name(kMeshName);
    REQUIRE(tc_mesh_is_valid(loaded));

    termin::Entity entity = result.scene.find_entity_by_name("RuntimeLoaderTestEntity");
    REQUIRE(entity.valid());
    result.scene.remove_entity(entity);

    tc_mesh_handle still_loaded = tc_mesh_find_by_name(kMeshName);
    CHECK(tc_mesh_is_valid(still_loaded));
}

TEST_CASE("RuntimePackageLoader loads packaged textures before dependent materials") {
    const std::filesystem::path root = make_package_root();
    write_test_package_with_texture(root);

    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
    REQUIRE(result.ok);
    REQUIRE(result.resources != nullptr);

    termin::TcTexture texture = termin::TcTexture::from_uuid(kTextureUuid);
    REQUIRE(texture.is_valid());
    CHECK_EQ(texture.width(), 2);
    CHECK_EQ(texture.height(), 1);
    CHECK_EQ(texture.channels(), 4);
    CHECK(texture.flip_x());
    CHECK_FALSE(texture.flip_y());
    CHECK(texture.transpose());
    CHECK_EQ(std::string(texture.name()), std::string(kTextureName));
    CHECK_EQ(std::filesystem::path(texture.source_path()), root / "textures" / "albedo.png");

    const auto* pixels = static_cast<const std::uint8_t*>(texture.data());
    REQUIRE(pixels != nullptr);
    CHECK_EQ(pixels[0], 0x10);
    CHECK_EQ(pixels[7], 0x80);

    termin::TcMaterial material = termin::TcMaterial::from_uuid(kMaterialUuid);
    REQUIRE(material.is_valid());
    tc_material_texture* binding = require_texture(material.default_phase(), "u_albedo_texture");
    tc_texture* bound_texture = tc_texture_get(binding->texture);
    REQUIRE(bound_texture != nullptr);
    CHECK_EQ(std::string(bound_texture->header.uuid), std::string(kTextureUuid));
}

TEST_CASE("RuntimePackageLoader diagnoses invalid packaged texture resources") {
    const std::filesystem::path root = make_package_root();
    write_test_package_with_texture(root);
    termin::tgfx2_set_shader_artifact_root("runtime-loader-failure-sentinel");

    write_text(root / "textures" / "test.texture.json", texture_spec("textures/missing.png"));
    termin::runtime::RuntimePackageLoadResult missing = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(missing.ok);
    CHECK(missing.message.find("source file not found") != std::string::npos);

    write_text(root / "textures" / "test.texture.json", texture_spec("../outside.png"));
    termin::runtime::RuntimePackageLoadResult escaping = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(escaping.ok);
    CHECK(escaping.message.find("dot segments") != std::string::npos);

    write_text(root / "textures" / "test.texture.json", texture_spec("textures/unsupported.bin"));
    write_binary(root / "textures" / "unsupported.bin", {0x01, 0x02, 0x03, 0x04});
    termin::runtime::RuntimePackageLoadResult unsupported = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(unsupported.ok);
    CHECK(unsupported.message.find("unsupported image format") != std::string::npos);

    write_text(root / "textures" / "test.texture.json", texture_spec("textures/malformed.png"));
    write_binary(
        root / "textures" / "malformed.png",
        {0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00}
    );
    termin::runtime::RuntimePackageLoadResult malformed = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(malformed.ok);
    CHECK(malformed.message.find("libpng") != std::string::npos);

    write_text(
        root / "textures" / "test.texture.json",
        replace_once(texture_spec(), "\"flip_x\": true", "\"flip_x\": 1")
    );
    termin::runtime::RuntimePackageLoadResult invalid_settings =
        termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(invalid_settings.ok);
    CHECK(invalid_settings.message.find("must be boolean") != std::string::npos);

    write_text(root / "textures" / "test.texture.json", texture_spec());
    write_text(
        root / "manifest.json",
        replace_once(manifest_with_packaged_texture(), kTextureUuid, "different-texture-uuid")
    );
    termin::runtime::RuntimePackageLoadResult mismatched_uuid =
        termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(mismatched_uuid.ok);
    CHECK(mismatched_uuid.message.find("manifest uuid does not match") != std::string::npos);
    CHECK(
        std::string(termin::tgfx2_get_shader_artifact_root()) ==
        "runtime-loader-failure-sentinel"
    );
    termin::tgfx2_set_shader_artifact_root("");
}

TEST_CASE("RuntimePackageLoader rejects manifest path traversal and platform separators") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    const std::vector<std::pair<std::string, std::string>> invalid_paths = {
        {"\"scene\": \"scene.json\"", "\"scene\": \"../scene.json\""},
        {"\"scene\": \"scene.json\"", "\"scene\": \".\\\\scene.json\""},
        {"\"path\": \"shaders/test.shader.json\"", "\"path\": \"/tmp/scene.json\""},
        {"\"path\": \"shaders/test.shader.json\"", "\"path\": \"C:\\\\outside.json\""},
    };
    for (const auto& [needle, replacement] : invalid_paths) {
        write_text(root / "manifest.json", replace_once(manifest(), needle, replacement));
        const termin::runtime::RuntimePackageLoadResult result =
            termin::runtime::load_runtime_package(root.string());
        CHECK_FALSE(result.ok);
        CHECK_FALSE(result.message.empty());
    }
}

TEST_CASE("RuntimePackageLoader follows only symlinks contained in the package") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    std::error_code error;
    std::filesystem::create_symlink(
        root / "shaders" / "test.shader.json",
        root / "shaders" / "inside.shader.json",
        error
    );
#ifdef _WIN32
    if (error.value() == 1314) {
        std::fprintf(stderr, "Skipping symlink containment check: Windows symlink privilege is unavailable\n");
        return;
    }
#endif
    REQUIRE_FALSE(error);
    write_text(
        root / "manifest.json",
        replace_once(
            manifest(),
            "\"path\": \"shaders/test.shader.json\"",
            "\"path\": \"shaders/inside.shader.json\""
        )
    );
    CHECK(termin::runtime::load_runtime_package(root.string()).ok);

    const std::filesystem::path outside = root.parent_path() / "termin-runtime-package-loader-outside.json";
    write_text(outside, shader_spec());
    std::filesystem::create_symlink(outside, root / "shaders" / "outside.shader.json", error);
    REQUIRE_FALSE(error);
    write_text(
        root / "manifest.json",
        replace_once(
            manifest(),
            "\"path\": \"shaders/test.shader.json\"",
            "\"path\": \"shaders/outside.shader.json\""
        )
    );
    const termin::runtime::RuntimePackageLoadResult result =
        termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(result.ok);
    CHECK_FALSE(result.message.empty());
    std::filesystem::remove(outside, error);
}
