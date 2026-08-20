#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include <components/collider_component.hpp>
#include <termin/bootstrap/bootstrap.hpp>
#include <termin/camera/orbit_camera_controller.hpp>
#include <termin/collision/collision_world.hpp>
#include <termin/entity/entity.hpp>
#include <termin/gui_native/ui_document_asset.hpp>
#include <termin/image/image_decode.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/render/sprite_asset.hpp>
#include <termin/render/tc_pipeline_template.hpp>
#include <termin/render/tc_scene_render_accessors.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin/scene/scene_manager.hpp>
#include <termin/scene/tc_scene_render_ext.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_shader_program_handle.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <core/tc_light_capability.h>
#include <core/tc_scene.h>
#include <core/tc_scene_extension_ids.h>
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
        std::filesystem::path root = std::filesystem::temp_directory_path() / "termin-runtime-package-loader-test";
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

    std::string shader_fragment_source() {
        return R"(
#version 330 core
uniform sampler2D u_albedo_texture;
uniform sampler2D u_normal_texture;
layout(std140) uniform MaterialParams {
    vec4 u_vec4;
    vec4 u_srgb_color;
    vec4 u_linear_color;
    float u_roughness;
    vec3 u_emissive;
    int u_enabled;
};
out vec4 FragColor;
void main() {
    FragColor = u_vec4 + u_srgb_color + u_linear_color;
}
)";
    }

    std::string json_string(const std::string& value) {
        std::string result = "\"";
        for (const char character : value) {
            switch (character) {
            case '\\':
                result += "\\\\";
                break;
            case '"':
                result += "\\\"";
                break;
            case '\n':
                result += "\\n";
                break;
            case '\r':
                result += "\\r";
                break;
            case '\t':
                result += "\\t";
                break;
            default:
                result += character;
                break;
            }
        }
        result += '"';
        return result;
    }

    std::string shader_spec() {
        std::ostringstream out;
        out << "{\n"
            << "  \"uuid\": \"" << kShaderUuid << "\",\n"
            << "  \"name\": \"RuntimeLoaderTestShader\",\n"
            << "  \"language\": \"glsl\",\n"
            << "  \"fragment_source_path\": \"shaders/test.frag\",\n"
            << "  \"features\": 1,\n"
            << "  \"shader_contract\": {\"schema_version\": 1, "
               "\"debug_name\": \"RuntimeLoaderTestShader\", \"vertex_inputs\": ["
               "{\"semantic\": \"position\", \"type\": 3, \"required\": true}, "
               "{\"semantic\": \"color\", \"type\": 3, \"required\": true}]},\n"
            << "  \"surface_producer\": {\n"
            << "    \"schema_version\": 1,\n"
            << "    \"contract_id\": \"termin.surface.standard-pbr\",\n"
            << "    \"contract_version\": 1,\n"
            << "    \"surface_type_name\": \"TerminStandardSurfaceV1\",\n"
            << "    \"evaluator_entry\": \"main\",\n"
            << "    \"evaluator_source\": " << json_string(shader_fragment_source()) << ",\n"
            << "    \"source_identity\": \"runtime-loader-test-surface\",\n"
            << "    \"fragment_inputs\": [{\"semantic\": \"world_pos\", \"type\": 3}],\n"
            << "    \"resources\": [{\"name\": \"material\", \"kind\": 1, "
               "\"scope\": 3, \"stage_mask\": 2, \"size\": 16, "
               "\"element_stride\": 0, \"fields\": [{\"name\": \"u_srgb_color\", "
               "\"type\": \"SrgbColor\", \"offset\": 0, \"size\": 16}]}]\n"
            << "  }\n"
            << "}\n";
        return out.str();
    }

    std::string shader_program_spec() {
        std::ostringstream out;
        out << "{\n"
            << "  \"schema_version\": 1,\n"
            << "  \"uuid\": \"" << kProgramUuid << "\",\n"
            << "  \"name\": \"RuntimeLoaderTestProgram\",\n"
            << "  \"source_path\": \"packaged-test\",\n"
            << "  \"language\": \"glsl\",\n"
            << "  \"features\": 1,\n"
            << "  \"properties\": [\n"
            << "    {\"name\": \"u_vec4\", \"property_type\": \"Vec4\", "
               "\"default\": [0.1, 0.2, 0.3, 0.4]},\n"
            << "    {\"name\": \"u_srgb_color\", \"property_type\": \"SrgbColor\", "
               "\"default\": [1.0, 0.5, 0.25, 1.0]},\n"
            << "    {\"name\": \"u_linear_color\", \"property_type\": \"LinearColor\", "
               "\"default\": [2.0, 1.5, 0.5, 0.75]},\n"
            << "    {\"name\": \"u_albedo_texture\", \"property_type\": \"Texture\", "
               "\"expected_encoding\": \"srgb\", \"default\": \"white\"},\n"
            << "    {\"name\": \"u_normal_texture\", \"property_type\": \"Texture\", "
               "\"expected_encoding\": \"linear\", \"default\": \"normal\"}\n"
            << "  ],\n"
            << "  \"phases\": [\n"
            << "    {\"phase_mark\": \"opaque\", \"priority\": 0, \"shader\": \"" << kShaderUuid
            << "\", \"state\": {\"polygon_mode\": 0, \"cull\": true, "
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
        out << "{\n"
            << "  \"uuid\": \"" << kMaterialUuid << "\",\n"
            << "  \"name\": \"RuntimeLoaderTestMaterial\",\n"
            << "  \"shader_program\": \"" << kProgramUuid << "\",\n"
            << "  \"phases\": [\n"
            << "    {\"shader\": \"" << kShaderUuid << "\", \"mark\": \"opaque\", \"priority\": 0}\n"
            << "  ],\n"
            << "  \"uniforms\": {\n"
            << "    \"u_vec4\": [0.1, 0.2, 0.3, 0.4],\n"
            << "    \"u_srgb_color\": [0.25, 0.5, 0.75, 1.0],\n"
            << "    \"u_linear_color\": [2.0, 1.5, 0.5, 0.75],\n"
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
  "version": 3,
  "world_controller": null,
  "entry_scene": "Scenes/Main.scene",
  "scenes": [
    {"identity": "Scenes/Main.scene", "path": "scene.json"}
  ],
  "resources": [
    {"type": "shader", "uuid": "shader-phase-12beb2a809af29f7", "path": "shaders/test.shader.json"},
    {"type": "shader_program", "uuid": "runtime-loader-test-program", "path": "shaders/test.shader-program.json"},
    {"type": "material", "uuid": "runtime-loader-test-material", "path": "materials/test.tmat.json"},
    {"type": "mesh", "uuid": "runtime-loader-test-mesh", "path": "meshes/test.tmesh.json"}
  ]
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
        out << "{\n"
            << "  \"uuid\": \"" << kTextureUuid << "\",\n"
            << "  \"name\": \"" << kTextureName << "\",\n"
            << "  \"source_path\": \"" << source_path << "\",\n"
            << "  \"import_settings\": {\"flip_x\": true, \"flip_y\": false, "
               "\"transpose\": true, \"encoding\": \"srgb\"}\n"
            << "}\n";
        return out.str();
    }

    std::string material_spec_with_asset_texture() {
        return replace_once(material_spec(),
                            "{\"kind\": \"builtin\", \"name\": \"white\"}",
                            std::string("{\"kind\": \"asset\", \"uuid\": \"") + kTextureUuid + "\"}");
    }

    std::string manifest_with_packaged_texture() {
        return R"({
  "version": 3,
  "world_controller": null,
  "entry_scene": "Scenes/Main.scene",
  "scenes": [
    {"identity": "Scenes/Main.scene", "path": "scene.json"}
  ],
  "resources": [
    {"type": "material", "uuid": "runtime-loader-test-material", "path": "materials/test.tmat.json"},
    {"type": "texture", "uuid": "runtime-loader-test-texture", "path": "textures/test.texture.json"},
    {"type": "mesh", "uuid": "runtime-loader-test-mesh", "path": "meshes/test.tmesh.json"},
    {"type": "shader", "uuid": "shader-phase-12beb2a809af29f7", "path": "shaders/test.shader.json"},
    {"type": "shader_program", "uuid": "runtime-loader-test-program", "path": "shaders/test.shader-program.json"}
  ]
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

    std::string collision_scene_json() {
        return R"({
  "uuid": "runtime-loader-collision-scene",
  "entities": [
    {
      "uuid": "runtime-loader-collider-entity",
      "name": "PackagedCollider",
      "visible": true,
      "enabled": true,
      "pose": {
        "position": [0.0, 0.0, 0.0],
        "rotation": [0.0, 0.0, 0.0, 1.0]
      },
      "scale": [1.0, 1.0, 1.0],
      "components": [
        {
          "type": "ColliderComponent",
          "data": {
            "collider_type": "Box",
            "box_size": [1.0, 2.0, 3.0],
            "collider_offset_enabled": false,
            "collider_offset_position": [0.0, 0.0, 0.0],
            "collider_offset_euler": [0.0, 0.0, 0.0]
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
        write_text(root / "shaders" / "test.shader-program.json", shader_program_spec());
        write_text(root / "shaders" / "test.frag", shader_fragment_source());
        write_text(root / "materials" / "test.tmat.json", material_spec());
        write_text(root / "meshes" / "test.tmesh.json", mesh_spec());
    }

    void write_test_package_with_texture(const std::filesystem::path& root) {
        write_test_package(root);
        write_text(root / "manifest.json", manifest_with_packaged_texture());
        write_text(root / "materials" / "test.tmat.json", material_spec_with_asset_texture());
        write_text(root / "textures" / "test.texture.json", texture_spec());
        const std::vector<std::uint8_t> rgba = {
            0x10,
            0x20,
            0x30,
            0x40,
            0x50,
            0x60,
            0x70,
            0x80,
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

TEST_CASE("RuntimePackageLoader minimal bootstrap loads core scenes and rejects omitted domains") {
    termin::bootstrap::shutdown_runtime();
    const std::filesystem::path root = make_package_root();
    write_text(root / "manifest.json", R"({
  "version": 3,
  "world_controller": null,
  "entry_scene": "Scenes/Main.scene",
  "scenes": [
    {"identity": "Scenes/Main.scene", "path": "scene.json"}
  ],
  "resources": []
}
)");
    write_text(root / "scene.json", R"({
  "uuid": "minimal-runtime-scene",
  "entities": [
    {
      "uuid": "minimal-runtime-entity",
      "name": "CoreEntity",
      "components": []
    }
  ]
}
)");

    termin::runtime::RuntimePackageLoadOptions options;
    options.bootstrap_profile = termin::bootstrap::RuntimeBootstrapProfile::Minimal;
    termin::runtime::RuntimePackageLoader loader;
    auto supported = loader.load(root.string(), options);
    REQUIRE(supported.ok);
    CHECK_EQ(supported.scene.entity_count(), 1);
    for (auto& scene : supported.scenes) {
        scene.scene.destroy();
    }
    supported.scene = {};
    supported.resources.reset();

    write_text(root / "scene.json", R"({
  "uuid": "unsupported-minimal-runtime-scene",
  "entities": [
    {
      "uuid": "unsupported-minimal-runtime-entity",
      "name": "RenderEntity",
      "components": [
        {"type": "MeshComponent", "data": {}}
      ]
    }
  ]
}
)");
    auto unsupported_component = loader.load(root.string(), options);
    CHECK_FALSE(unsupported_component.ok);
    CHECK(unsupported_component.message.find("MeshComponent") != std::string::npos);
    CHECK(unsupported_component.message.find("minimal runtime profile") != std::string::npos);

    write_text(root / "scene.json", R"({"uuid": "minimal-runtime-scene", "entities": []})");
    write_text(root / "manifest.json", R"({
  "version": 3,
  "world_controller": null,
  "entry_scene": "Scenes/Main.scene",
  "scenes": [
    {"identity": "Scenes/Main.scene", "path": "scene.json"}
  ],
  "resources": [
    {"type": "mesh", "uuid": "unsupported-mesh", "path": "meshes/test.tmesh.json"}
  ]
}
)");
    auto unsupported_resource = loader.load(root.string(), options);
    CHECK_FALSE(unsupported_resource.ok);
    CHECK(unsupported_resource.message.find("resource type 'mesh'") != std::string::npos);

    termin::bootstrap::shutdown_runtime();
}

TEST_CASE("RuntimePackageLoader restores OrbitCameraController horizon lock") {
    termin::bootstrap::shutdown_runtime();
    const std::filesystem::path root = make_package_root();
    write_text(root / "manifest.json", R"({
  "version": 3,
  "world_controller": null,
  "entry_scene": "Scenes/Main.scene",
  "scenes": [
    {"identity": "Scenes/Main.scene", "path": "scene.json"}
  ],
  "resources": []
}
)");
    write_text(root / "scene.json", R"({
  "uuid": "orbit-camera-runtime-scene",
  "entities": [
    {
      "uuid": "orbit-camera-runtime-entity",
      "name": "RuntimeCamera",
      "components": [
        {"type": "CameraComponent", "data": {}},
        {"type": "OrbitCameraController", "data": {"horizon_lock": false}}
      ]
    }
  ]
}
)");

    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
    REQUIRE(result.ok);
    termin::Entity camera = result.scene.find_entity_by_name("RuntimeCamera");
    REQUIRE(camera.valid());
    termin::OrbitCameraController* controller = camera.get_component<termin::OrbitCameraController>();
    REQUIRE(controller != nullptr);
    CHECK_FALSE(controller->horizon_lock);

    for (auto& scene : result.scenes) {
        scene.scene.destroy();
    }
    result.scene = {};
    result.resources.reset();
    termin::bootstrap::shutdown_runtime();
}

TEST_CASE("RuntimePackageLoader attaches rendering host extensions before component deserialization") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);
    write_text(root / "scene.json", collision_scene_json());

    termin::runtime::RuntimePackageLoadOptions options;
    termin::bootstrap::bootstrap_runtime();
    options.scene_extensions = termin::default_scene_extension_ids();
    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string(), options);

    REQUIRE(result.ok);
    REQUIRE(result.scene.valid());
    CHECK(tc_scene_ext_has(result.scene.handle(), TC_SCENE_EXT_TYPE_RENDER_MOUNT));
    CHECK(tc_scene_ext_has(result.scene.handle(), TC_SCENE_EXT_TYPE_RENDER_STATE));
    CHECK(tc_scene_ext_has(result.scene.handle(), TC_SCENE_EXT_TYPE_COLLISION_WORLD));
    termin::collision::CollisionWorld* world = termin::collision::CollisionWorld::from_scene(result.scene.handle());
    REQUIRE(world != nullptr);

    termin::Entity packaged_entity = result.scene.find_entity_by_name("PackagedCollider");
    REQUIRE(packaged_entity.valid());
    termin::ColliderComponent* packaged_collider = packaged_entity.get_component<termin::ColliderComponent>();
    REQUIRE(packaged_collider != nullptr);
    REQUIRE(packaged_collider->attached_collider() != nullptr);
    CHECK(world->contains(packaged_collider->attached_collider()));
    CHECK_EQ(world->size(), 1u);

    termin::Entity dynamic_entity = result.scene.create_entity("DynamicCollider");
    auto* dynamic_collider = new termin::ColliderComponent();
    dynamic_entity.add_component(dynamic_collider);
    REQUIRE(dynamic_collider->attached_collider() != nullptr);
    CHECK(world->contains(dynamic_collider->attached_collider()));
    CHECK_EQ(world->size(), 2u);
}

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
    REQUIRE_EQ(program.get()->property_count, 5u);
    CHECK_EQ(std::string(program.get()->properties[0].property_type), "Vec4");
    CHECK_EQ(std::string(program.get()->properties[1].property_type), "SrgbColor");
    CHECK_EQ(std::string(program.get()->properties[2].property_type), "LinearColor");
    CHECK(program.get()->properties[3].has_expected_encoding != 0);
    CHECK(program.get()->properties[3].expected_encoding == TC_TEXTURE_ENCODING_SRGB);
    CHECK(program.get()->properties[4].expected_encoding == TC_TEXTURE_ENCODING_LINEAR);
    CHECK_EQ(program.get()->phase_count, 1u);
    tc_shader* program_phase_shader = tc_shader_get(program.get()->phases[0].shader);
    REQUIRE(program_phase_shader != nullptr);
    CHECK_EQ(std::string(program_phase_shader->uuid), std::string(kShaderUuid));
    tc_material_phase* phase = material.default_phase();
    REQUIRE(phase != nullptr);

    termin::TcShader shader = termin::TcShader::from_uuid(kShaderUuid);
    REQUIRE(shader.is_valid());
    CHECK(shader.has_feature(TC_SHADER_FEATURE_LIGHTING_UBO));
    REQUIRE(tc_shader_has_contract(shader.get()));
    tc_shader_contract_view shader_contract{};
    REQUIRE(tc_shader_get_contract_view(shader.get(), &shader_contract));
    CHECK_EQ(shader_contract.source_kind, TC_SHADER_CONTRACT_SOURCE_DECLARED);
    REQUIRE_EQ(shader_contract.vertex_input_count, 2u);
    CHECK_EQ(std::string(shader_contract.vertex_inputs[0].semantic), std::string("position"));
    CHECK_EQ(std::string(shader_contract.vertex_inputs[1].semantic), std::string("color"));
    REQUIRE(shader.has_surface_producer());
    tc_shader_surface_producer_view producer{};
    REQUIRE(tc_shader_get_surface_producer_view(shader.get(), &producer));
    CHECK_EQ(std::string(producer.contract_id), std::string("termin.surface.standard-pbr"));
    CHECK_EQ(producer.contract_version, 1u);
    REQUIRE_EQ(producer.fragment_input_count, 1u);
    CHECK_EQ(std::string(producer.fragment_inputs[0].semantic), std::string("world_pos"));
    REQUIRE_EQ(producer.resource_count, 1u);
    CHECK_EQ(std::string(producer.resources[0].name), std::string("material"));
    REQUIRE_EQ(producer.resources[0].field_count, 1u);
    CHECK_EQ(std::string(producer.resources[0].fields[0].name), std::string("u_srgb_color"));

    const tc_material_ubo_entry* reflected = tc_shader_material_ubo_entries(shader.get());
    REQUIRE(reflected != nullptr);
    REQUIRE_EQ(tc_shader_material_ubo_entry_count(shader.get()), 6u);
    CHECK_EQ(std::string(reflected[0].property_type), "Vec4");
    CHECK_EQ(std::string(reflected[1].property_type), "SrgbColor");
    CHECK_EQ(std::string(reflected[2].property_type), "LinearColor");

    tc_uniform_value* vec4 = require_uniform(phase, "u_vec4", TC_UNIFORM_VEC4);
    CHECK(std::fabs(vec4->data.v4[0] - 0.1f) < 0.0001f);
    CHECK(std::fabs(vec4->data.v4[3] - 0.4f) < 0.0001f);

    tc_uniform_value* color = require_uniform(phase, "u_srgb_color", TC_UNIFORM_SRGB_COLOR);
    CHECK(std::fabs(color->data.srgb_color.r - 0.25f) < 0.0001f);
    CHECK(std::fabs(color->data.srgb_color.g - 0.5f) < 0.0001f);
    CHECK(std::fabs(color->data.srgb_color.b - 0.75f) < 0.0001f);
    CHECK(std::fabs(color->data.srgb_color.a - 1.0f) < 0.0001f);

    tc_uniform_value* linear = require_uniform(phase, "u_linear_color", TC_UNIFORM_LINEAR_COLOR);
    CHECK(std::fabs(linear->data.linear_color.r - 2.0f) < 0.0001f);
    CHECK(std::fabs(linear->data.linear_color.g - 1.5f) < 0.0001f);
    CHECK(std::fabs(linear->data.linear_color.a - 0.75f) < 0.0001f);

    tc_uniform_value* roughness = require_uniform(phase, "u_roughness", TC_UNIFORM_FLOAT);
    CHECK(std::fabs(roughness->data.f - 0.42f) < 0.0001f);

    tc_uniform_value* emissive = require_uniform(phase, "u_emissive", TC_UNIFORM_VEC3);
    CHECK(std::fabs(emissive->data.v3[0] - 0.1f) < 0.0001f);
    CHECK(std::fabs(emissive->data.v3[1] - 0.2f) < 0.0001f);
    CHECK(std::fabs(emissive->data.v3[2] - 0.3f) < 0.0001f);

    tc_uniform_value* enabled = require_uniform(phase, "u_enabled", TC_UNIFORM_BOOL);
    CHECK_EQ(enabled->data.i, 1);

    tc_material_texture* albedo_slot = require_texture(phase, "u_albedo_texture");
    tc_material_texture* normal_slot = require_texture(phase, "u_normal_texture");
    CHECK(albedo_slot->has_expected_encoding != 0);
    CHECK(normal_slot->has_expected_encoding != 0);
    CHECK_EQ(albedo_slot->expected_encoding, TC_TEXTURE_ENCODING_SRGB);
    CHECK_EQ(normal_slot->expected_encoding, TC_TEXTURE_ENCODING_LINEAR);
    REQUIRE(tc_texture_get(albedo_slot->texture) != nullptr);
    REQUIRE(tc_texture_get(normal_slot->texture) != nullptr);
    CHECK_EQ(tc_texture_get(albedo_slot->texture)->encoding, TC_TEXTURE_ENCODING_SRGB);
    CHECK_EQ(tc_texture_get(normal_slot->texture)->encoding, TC_TEXTURE_ENCODING_LINEAR);

    tc_scene_handle scene = result.scene.handle();
    CHECK_EQ(tc_scene_count_components_of_type(scene, "LightComponent"), 1);

    tc_component_cap_id light_cap = tc_light_capability_id();
    REQUIRE(light_cap != TC_COMPONENT_CAPABILITY_INVALID_ID);
    CHECK_EQ(tc_scene_capability_count(scene, light_cap), 1);

    LightProbe probe;
    tc_scene_foreach_with_capability(
        scene, light_cap, collect_test_light, &probe, TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);
    REQUIRE_EQ(probe.count, 1);
    CHECK_EQ(probe.first.type, TC_LIGHT_DIRECTIONAL);
    CHECK(std::fabs(probe.first.color[0] - 0.8) < 0.0001);
    CHECK(std::fabs(probe.first.color[1] - 0.9) < 0.0001);
    CHECK(std::fabs(probe.first.color[2] - 1.0) < 0.0001);
    CHECK(std::fabs(probe.first.intensity - 3.5) < 0.0001);

    tc_scene_lighting* lighting = termin::scene_lighting(result.scene);
    REQUIRE(lighting != nullptr);
    CHECK(std::fabs(lighting->ambient_color.r - 0.7f) < 0.0001f);
    CHECK(std::fabs(lighting->ambient_color.g - 0.8f) < 0.0001f);
    CHECK(std::fabs(lighting->ambient_color.b - 0.9f) < 0.0001f);
    CHECK(std::fabs(lighting->ambient_intensity - 0.33f) < 0.0001f);
}

TEST_CASE("RuntimePackageLoader exposes packaged builtin shader root") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);
    write_text(root / "manifest.json",
               replace_once(manifest(),
                            "\"resources\":",
                            "\"builtin_shader_contract\": {"
                            "\"version\": 1,"
                            "\"catalog\": \"builtin_shaders/engine-shader-catalog.json\","
                            "\"shaders\": [{\"uuid\": \"termin-engine-test\", \"artifacts\": {}}]"
                            "},"
                            "\"resources\":"));
    std::filesystem::create_directories(root / "builtin_shaders");
    write_text(root / "builtin_shaders" / "engine-shader-catalog.json", R"({"version":1,"shaders":[]})");

    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());

    REQUIRE(result.ok);
    CHECK(result.shader_runtime.builtin_shader_root == (root / "builtin_shaders").string());
}

TEST_CASE("RuntimePackageLoader releases compiled pipelines for a repeated runtime session") {
    const std::filesystem::path root = make_package_root();
    constexpr const char* pipeline_uuid = "runtime-loader-compiled-pipeline";

    const tc_pipeline_template_payload_desc descriptor = {
        TC_PIPELINE_TEMPLATE_DESCRIPTOR_VERSION,
        TC_PIPELINE_EXECUTION_SINGLE_VIEW,
        "Runtime Compiled Pipeline",
        nullptr,
        0,
        nullptr,
        0,
        nullptr,
        0,
        nullptr,
        0,
    };
    const tc_pipeline_template_handle source_handle =
        tc_pipeline_template_create("runtime-loader-compiled-pipeline-source", "source");
    tc_pipeline_template* source = tc_pipeline_template_get(source_handle);
    REQUIRE(source != nullptr);
    REQUIRE(tc_pipeline_template_set_payload(source, &descriptor));
    const size_t payload_size = tc_pipeline_template_serialize(source, nullptr, 0);
    REQUIRE(payload_size > 0);
    std::vector<std::uint8_t> payload(payload_size);
    REQUIRE_EQ(tc_pipeline_template_serialize(source, payload.data(), payload.size()), payload_size);
    REQUIRE(tc_pipeline_template_remove(source_handle));

    write_binary(root / "pipelines" / "compiled.pipeline-template", payload);
    write_text(root / "manifest.json", R"({
  "version": 3,
  "world_controller": null,
  "entry_scene": "Scenes/Main.scene",
  "scenes": [
    {"identity": "Scenes/Main.scene", "path": "scene.json"}
  ],
  "resources": [
    {"type": "pipeline", "uuid": "runtime-loader-compiled-pipeline", "name": "Runtime Compiled Pipeline", "path": "pipelines/compiled.pipeline-template"}
  ]
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

    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
    REQUIRE(result.ok);
    REQUIRE(result.resources != nullptr);
    const tc_pipeline_template_handle loaded = tc_pipeline_template_find(pipeline_uuid);
    REQUIRE(tc_pipeline_template_is_valid(loaded));
    const tc_pipeline_template* loaded_template = tc_pipeline_template_get(loaded);
    REQUIRE(loaded_template != nullptr);
    CHECK_EQ(std::string(loaded_template->header.name), "Runtime Compiled Pipeline");
    CHECK_EQ(tc_scene_pipeline_template_count(result.scene.handle()), 1u);
    CHECK(tc_pipeline_template_handle_eq(tc_scene_pipeline_template_at(result.scene.handle(), 0), loaded));

    termin::TcPipelineTemplate loaded_template_ref(loaded);
    termin::RenderPipeline runtime_pipeline(loaded_template_ref);
    REQUIRE(runtime_pipeline.is_valid());

    // Runtime execution objects must go first, followed by the package-owned
    // scenes and canonical resources. This is the Android pause/resume order.
    runtime_pipeline.destroy();
    loaded_template_ref = {};
    result.destroy();
    CHECK_FALSE(tc_pipeline_template_is_valid(loaded));

    termin::runtime::RuntimePackageLoadResult resumed = termin::runtime::load_runtime_package(root.string());
    REQUIRE(resumed.ok);
    CHECK(tc_pipeline_template_is_valid(tc_pipeline_template_find(pipeline_uuid)));
    resumed.destroy();
}

TEST_CASE("RuntimePackageLoader registers native UI documents before the scene") {
    const std::filesystem::path root = make_package_root();
    std::filesystem::create_directories(root / "ui");
    constexpr const char* ui_uuid = "runtime-native-ui";
    const std::string source = R"(
uiscript: 2
root:
  type: termin.gui.Panel
  name: runtime_root
  background_color: [0.1, 0.2, 0.3, 1]
)";
    const std::string compiled = termin::gui_native::TcUiDocumentAsset::compile_source_json(
        ui_uuid, "Runtime UI", "UI/runtime.uiscript", source);
    write_text(root / "ui" / "runtime.ui-document.json", compiled);
    write_text(root / "manifest.json", R"({
  "version": 3,
  "world_controller": null,
  "entry_scene": "Scenes/Main.scene",
  "scenes": [
    {"identity": "Scenes/Main.scene", "path": "scene.json"}
  ],
  "resources": [
    {"type": "ui_document", "uuid": "runtime-native-ui", "name": "Runtime UI", "path": "ui/runtime.ui-document.json"}
  ]
}
)");
    write_text(root / "scene.json", R"({
  "uuid": "runtime-native-ui-scene",
  "entities": []
}
)");

    termin::gui_native::TcUiDocumentAsset::clear_registry_for_tests();
    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());

    REQUIRE(result.ok);
    REQUIRE(result.resources != nullptr);
    const auto asset = termin::gui_native::TcUiDocumentAsset::from_uuid(ui_uuid);
    REQUIRE(asset.valid());
    const auto recipe = asset.resolve();
    REQUIRE(recipe != nullptr);
    CHECK_EQ(recipe->source_identity(), "UI/runtime.uiscript");
    CHECK_EQ(recipe->type_dependencies().size(), 1u);
    auto document = asset.instantiate();
    CHECK_EQ(document.root().type_name, "termin.gui.Panel");
    termin::gui_native::TcUiDocumentAsset::clear_registry_for_tests();
}

TEST_CASE("RuntimePackageLoader requires an explicit supported shader language") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    write_text(root / "shaders" / "test.shader.json", replace_once(shader_spec(), "  \"language\": \"glsl\",\n", ""));
    termin::runtime::RuntimePackageLoadResult missing = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(missing.ok);
    CHECK(missing.message.find("has no explicit language") != std::string::npos);

    write_text(root / "shaders" / "test.shader.json",
               replace_once(shader_spec(), "\"language\": \"glsl\"", "\"language\": \"spirv\""));
    termin::runtime::RuntimePackageLoadResult unsupported = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(unsupported.ok);
    CHECK(unsupported.message.find("unsupported language 'spirv'") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader rejects incompatible shader program schema") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);
    write_text(root / "shaders" / "test.shader-program.json",
               replace_once(shader_program_spec(), "\"schema_version\": 1", "\"schema_version\": 99"));

    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(result.ok);
    CHECK(result.message.find("requires schema_version 1") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader rejects legacy and unknown shader property kinds") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    write_text(root / "shaders" / "test.shader-program.json",
               replace_once(shader_program_spec(), "\"property_type\": \"Vec4\"", "\"property_type\": \"Color\""));
    termin::runtime::RuntimePackageLoadResult legacy = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(legacy.ok);
    CHECK(legacy.message.find("legacy property_type 'Color'") != std::string::npos);
    CHECK(legacy.message.find("SrgbColor") != std::string::npos);
    CHECK(legacy.message.find("LinearColor") != std::string::npos);

    write_text(
        root / "shaders" / "test.shader-program.json",
        replace_once(shader_program_spec(), "\"property_type\": \"Vec4\"", "\"property_type\": \"DisplayColor\""));
    termin::runtime::RuntimePackageLoadResult unknown = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(unknown.ok);
    CHECK(unknown.message.find("unsupported property_type 'DisplayColor'") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader validates typed color defaults") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    write_text(
        root / "shaders" / "test.shader-program.json",
        replace_once(shader_program_spec(), "\"default\": [1.0, 0.5, 0.25, 1.0]", "\"default\": [1.0, 0.5, 0.25]"));
    termin::runtime::RuntimePackageLoadResult short_color = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(short_color.ok);
    CHECK(short_color.message.find("SrgbColor") != std::string::npos);
    CHECK(short_color.message.find("exactly 4 components") != std::string::npos);

    write_text(root / "shaders" / "test.shader-program.json",
               replace_once(shader_program_spec(), "\"default\": [2.0, 1.5, 0.5, 0.75]", "\"default\": \"white\""));
    termin::runtime::RuntimePackageLoadResult wrong_shape = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(wrong_shape.ok);
    CHECK(wrong_shape.message.find("LinearColor") != std::string::npos);
    CHECK(wrong_shape.message.find("exactly 4 components") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader rejects material values that violate typed color schema") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    write_text(root / "materials" / "test.tmat.json",
               replace_once(
                   material_spec(), "\"u_srgb_color\": [0.25, 0.5, 0.75, 1.0]", "\"u_srgb_color\": [0.25, 0.5, 0.75]"));
    termin::runtime::RuntimePackageLoadResult wrong_arity = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(wrong_arity.ok);
    CHECK(wrong_arity.message.find("u_srgb_color") != std::string::npos);
    CHECK(wrong_arity.message.find("SrgbColor") != std::string::npos);

    write_text(root / "materials" / "test.tmat.json",
               replace_once(material_spec(), "\"u_linear_color\": [2.0, 1.5, 0.5, 0.75]", "\"u_linear_color\": 0.5"));
    termin::runtime::RuntimePackageLoadResult wrong_shape = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(wrong_shape.ok);
    CHECK(wrong_shape.message.find("u_linear_color") != std::string::npos);
    CHECK(wrong_shape.message.find("LinearColor") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader accepts shader texture property without encoding constraint") {
    const std::filesystem::path root = make_package_root();
    write_test_package_with_texture(root);

    write_text(root / "shaders" / "test.shader-program.json",
               replace_once(shader_program_spec(), ", \"expected_encoding\": \"srgb\"", ""));
    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
    REQUIRE(result.ok);

    termin::TcShaderProgram program = termin::TcShaderProgram::find(kProgramUuid);
    REQUIRE(program.is_valid());
    REQUIRE(program.get()->property_count > 3);
    CHECK(program.get()->properties[3].has_expected_encoding == 0);

    termin::TcMaterial material = termin::TcMaterial::from_uuid(kMaterialUuid);
    REQUIRE(material.is_valid());
    tc_material_texture* slot = require_texture(material.default_phase(), "u_albedo_texture");
    CHECK(slot->is_declared != 0);
    CHECK(slot->has_expected_encoding == 0);
    tc_texture* texture = tc_texture_get(slot->texture);
    REQUIRE(texture != nullptr);
    CHECK(texture->encoding == TC_TEXTURE_ENCODING_SRGB);
}

TEST_CASE("RuntimePackageLoader rejects invalid shader texture property encoding") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    write_text(root / "shaders" / "test.shader-program.json",
               replace_once(
                   shader_program_spec(), "\"expected_encoding\": \"srgb\"", "\"expected_encoding\": \"display-p3\""));
    termin::runtime::RuntimePackageLoadResult invalid = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(invalid.ok);
    CHECK(invalid.message.find("must be 'srgb' or 'linear'") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader fails closed when the entry scene is missing or invalid") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    std::filesystem::remove(root / "scene.json");
    termin::runtime::RuntimePackageLoadResult missing = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(missing.ok);
    CHECK_FALSE(missing.scene.valid());
    CHECK(missing.message.find("failed to open file") != std::string::npos ||
          missing.message.find("failed to canonicalize runtime package path") != std::string::npos);
    CHECK(missing.message.find("scene.json") != std::string::npos);

    write_text(root / "scene.json", "{ invalid scene json");
    termin::runtime::RuntimePackageLoadResult invalid = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(invalid.ok);
    CHECK_FALSE(invalid.scene.valid());
    CHECK(invalid.message.find("failed to parse packaged runtime scene") != std::string::npos);
    CHECK(invalid.message.find("scene.json") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader preserves strict optional WorldController selection") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);
    write_text(root / "manifest.json",
               replace_once(
                   manifest(),
                   "\"world_controller\": null",
                   "\"world_controller\": {\"module\": \"game\", \"type\": \"game.ProjectDirector\"}"));

    termin::runtime::RuntimePackageLoadResult selected =
        termin::runtime::load_runtime_package(root.string());
    REQUIRE(selected.ok);
    REQUIRE(selected.world_controller.has_value());
    CHECK_EQ(selected.world_controller->module, "game");
    CHECK_EQ(selected.world_controller->type, "game.ProjectDirector");
    selected.destroy();
    CHECK_FALSE(selected.world_controller.has_value());

    write_text(root / "manifest.json",
               replace_once(manifest(),
                            "\"world_controller\": null,\n",
                            ""));
    const auto missing = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(missing.ok);
    CHECK(missing.message.find("explicitly define world_controller") != std::string::npos);

    write_text(root / "manifest.json",
               replace_once(manifest(),
                            "\"world_controller\": null",
                            "\"world_controller\": {\"module\": \" game \", \"type\": \"Director\"}"));
    const auto malformed = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(malformed.ok);
    CHECK(malformed.message.find("non-empty trimmed strings") != std::string::npos);
}

TEST_CASE("RuntimePackageLoader resolves and transitions between packaged scene identities") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);
    std::filesystem::create_directories(root / "scenes");
    write_text(root / "scenes" / "Menu.scene.json", R"({
  "uuid": "runtime-loader-menu-scene",
  "entities": []
}
)");
    write_text(root / "manifest.json",
               replace_once(manifest(),
                            "{\"identity\": \"Scenes/Main.scene\", \"path\": \"scene.json\"}",
                            "{\"identity\": \"Scenes/Main.scene\", \"path\": \"scene.json\"},\n"
                            "    {\"identity\": \"Scenes/Menu.scene\", "
                            "\"path\": \"scenes/Menu.scene.json\"}"));

    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());

    REQUIRE(result.ok);
    CHECK_EQ(result.entry_scene_identity, "Scenes/Main.scene");
    REQUIRE_EQ(result.scenes.size(), 2u);
    REQUIRE(result.find_scene("Scenes/Main.scene").valid());
    REQUIRE(result.find_scene("Scenes/Menu.scene").valid());
    CHECK_FALSE(result.find_scene("Scenes/Missing.scene").valid());
    CHECK_EQ(result.find_scene("Scenes/Menu.scene").source_path(), (root / "scenes" / "Menu.scene.json").string());

    termin::SceneManager manager;
    for (const termin::runtime::RuntimePackageScene& packaged_scene : result.scenes) {
        const termin::SceneKey key{packaged_scene.identity, termin::SceneRole::Runtime};
        manager.register_scene(key, packaged_scene.scene.handle());
        manager.set_mode(key, TC_SCENE_MODE_INACTIVE);
    }
    const termin::SceneKey main_key{"Scenes/Main.scene", termin::SceneRole::Runtime};
    const termin::SceneKey menu_key{"Scenes/Menu.scene", termin::SceneRole::Runtime};
    manager.set_mode(main_key, TC_SCENE_MODE_PLAY);
    CHECK_EQ(manager.get_mode(main_key), TC_SCENE_MODE_PLAY);
    CHECK_EQ(manager.get_mode(menu_key), TC_SCENE_MODE_INACTIVE);

    manager.set_mode(main_key, TC_SCENE_MODE_INACTIVE);
    manager.set_mode(menu_key, TC_SCENE_MODE_PLAY);
    CHECK_EQ(manager.get_mode(main_key), TC_SCENE_MODE_INACTIVE);
    CHECK_EQ(manager.get_mode(menu_key), TC_SCENE_MODE_PLAY);
    manager.unregister_scene(main_key);
    manager.unregister_scene(menu_key);
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
    CHECK(texture.encoding() == tgfx::TextureEncoding::SRGB);
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

TEST_CASE("RuntimePackageLoader binds material texture encoding mismatch") {
    const std::filesystem::path root = make_package_root();
    write_test_package_with_texture(root);
    write_text(root / "textures" / "test.texture.json",
               replace_once(texture_spec(), "\"encoding\": \"srgb\"", "\"encoding\": \"linear\""));

    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
    REQUIRE(result.ok);

    termin::TcMaterial material = termin::TcMaterial::from_uuid(kMaterialUuid);
    REQUIRE(material.is_valid());
    tc_material_texture* binding = require_texture(material.default_phase(), "u_albedo_texture");
    tc_texture* bound_texture = tc_texture_get(binding->texture);
    REQUIRE(bound_texture != nullptr);
    CHECK_EQ(bound_texture->encoding, TC_TEXTURE_ENCODING_LINEAR);
}

TEST_CASE("RuntimePackageLoader diagnoses invalid packaged texture resources") {
    const std::filesystem::path root = make_package_root();
    write_test_package_with_texture(root);
    termin::tgfx2_set_shader_artifact_root("runtime-loader-failure-sentinel");

    write_text(root / "textures" / "test.texture.json", texture_spec("textures/missing.png"));
    termin::runtime::RuntimePackageLoadResult missing = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(missing.ok);
    CHECK(missing.message.find("source file not found") != std::string::npos ||
          missing.message.find("failed to canonicalize runtime package path") != std::string::npos);

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
    write_binary(root / "textures" / "malformed.png", {0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00});
    termin::runtime::RuntimePackageLoadResult malformed = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(malformed.ok);
    CHECK(malformed.message.find("libpng") != std::string::npos);

    write_text(root / "textures" / "test.texture.json",
               replace_once(texture_spec(), "\"flip_x\": true", "\"flip_x\": 1"));
    termin::runtime::RuntimePackageLoadResult invalid_settings = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(invalid_settings.ok);
    CHECK(invalid_settings.message.find("must be boolean") != std::string::npos);

    write_text(root / "textures" / "test.texture.json",
               replace_once(texture_spec(), "\"encoding\": \"srgb\"", "\"encoding\": \"display-p3\""));
    termin::runtime::RuntimePackageLoadResult invalid_encoding = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(invalid_encoding.ok);
    CHECK(invalid_encoding.message.find("must be 'srgb' or 'linear'") != std::string::npos);

    write_text(root / "textures" / "test.texture.json", replace_once(texture_spec(), ", \"encoding\": \"srgb\"", ""));
    termin::runtime::RuntimePackageLoadResult missing_encoding = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(missing_encoding.ok);
    CHECK(missing_encoding.message.find("field 'encoding' must be a string") != std::string::npos);

    write_text(root / "textures" / "test.texture.json", texture_spec());
    write_text(root / "manifest.json",
               replace_once(manifest_with_packaged_texture(), kTextureUuid, "different-texture-uuid"));
    termin::runtime::RuntimePackageLoadResult mismatched_uuid = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(mismatched_uuid.ok);
    CHECK(mismatched_uuid.message.find("manifest uuid does not match") != std::string::npos);
    CHECK(std::string(termin::tgfx2_get_shader_artifact_root()) == "runtime-loader-failure-sentinel");
    termin::tgfx2_set_shader_artifact_root("");
}

TEST_CASE("RuntimePackageLoader loads SpriteAsset after its texture") {
    const std::filesystem::path root = make_package_root();
    write_test_package_with_texture(root);
    std::filesystem::create_directories(root / "sprites");
    write_text(root / "sprites" / "hero.sprite.json", R"({
  "format": "termin.sprite",
  "version": 1,
  "uuid": "runtime-loader-test-sprite",
  "name": "Hero",
  "texture": {"uuid": "runtime-loader-test-texture"},
  "region": [0, 0, 1, 1],
  "source_size": [1, 1],
  "pivot": [0.5, 0.5],
  "pixels_per_unit": 16.0,
  "sampling": "nearest"
}
)");
    write_text(root / "manifest.json",
               replace_once(manifest_with_packaged_texture(),
                            "    {\"type\": \"material\"",
                            "    {\"type\": \"sprite_asset\", \"uuid\": \"runtime-loader-test-sprite\", "
                            "\"path\": \"sprites/hero.sprite.json\"},\n"
                            "    {\"type\": \"material\""));

    termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
    REQUIRE(result.ok);
    termin::TcSpriteAsset sprite = termin::TcSpriteAsset::from_uuid("runtime-loader-test-sprite");
    REQUIRE(sprite.is_loaded());
    REQUIRE(sprite.get() != nullptr);
    CHECK_EQ(sprite.get()->texture_uuid, std::string(kTextureUuid));
    CHECK_EQ(sprite.get()->region.width, 1);
    CHECK_EQ(sprite.get()->pixels_per_unit, 16.0f);
    CHECK(sprite.get()->sampling == termin::SpriteSampling::Nearest);
}

TEST_CASE("RuntimePackageLoader rejects manifest path traversal and platform separators") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    const std::vector<std::pair<std::string, std::string>> invalid_paths = {
        {"\"path\": \"scene.json\"", "\"path\": \"../scene.json\""},
        {"\"path\": \"scene.json\"", "\"path\": \".\\\\scene.json\""},
        {"\"path\": \"shaders/test.shader.json\"", "\"path\": \"/tmp/scene.json\""},
        {"\"path\": \"shaders/test.shader.json\"", "\"path\": \"C:\\\\outside.json\""},
    };
    for (const auto& [needle, replacement] : invalid_paths) {
        write_text(root / "manifest.json", replace_once(manifest(), needle, replacement));
        const termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
        CHECK_FALSE(result.ok);
        CHECK_FALSE(result.message.empty());
    }
}

TEST_CASE("RuntimePackageLoader follows only symlinks contained in the package") {
    const std::filesystem::path root = make_package_root();
    write_test_package(root);

    std::error_code error;
    std::filesystem::create_symlink(
        root / "shaders" / "test.shader.json", root / "shaders" / "inside.shader.json", error);
#ifdef _WIN32
    if (error.value() == 1314) {
        std::fprintf(stderr, "Skipping symlink containment check: Windows symlink privilege is unavailable\n");
        return;
    }
#endif
    REQUIRE_FALSE(error);
    write_text(
        root / "manifest.json",
        replace_once(manifest(), "\"path\": \"shaders/test.shader.json\"", "\"path\": \"shaders/inside.shader.json\""));
    CHECK(termin::runtime::load_runtime_package(root.string()).ok);

    const std::filesystem::path outside = root.parent_path() / "termin-runtime-package-loader-outside.json";
    write_text(outside, shader_spec());
    std::filesystem::create_symlink(outside, root / "shaders" / "outside.shader.json", error);
    REQUIRE_FALSE(error);
    write_text(root / "manifest.json",
               replace_once(
                   manifest(), "\"path\": \"shaders/test.shader.json\"", "\"path\": \"shaders/outside.shader.json\""));
    const termin::runtime::RuntimePackageLoadResult result = termin::runtime::load_runtime_package(root.string());
    CHECK_FALSE(result.ok);
    CHECK_FALSE(result.message.empty());
    std::filesystem::remove(outside, error);
}

TEST_CASE("RuntimePackageLoader validates the same package through directory and blob readers") {
    termin::runtime::RuntimePackageLoader loader;
    termin::runtime::RuntimePackageLoadResult directory = loader.load(TERMIN_RUNTIME_READER_FIXTURE_ROOT);
    REQUIRE(directory.ok);

    std::ifstream input(TERMIN_RUNTIME_READER_FIXTURE_BLOB, std::ios::binary);
    REQUIRE(static_cast<bool>(input));
    auto blob = std::make_shared<std::vector<std::uint8_t>>(std::istreambuf_iterator<char>(input),
                                                            std::istreambuf_iterator<char>());
    REQUIRE_FALSE(blob->empty());
    termin::runtime::RuntimePackageLoadResult packed =
        loader.load(termin::runtime::open_runtime_package_blob(blob, "reader-test-blob"));
    REQUIRE(packed.ok);
    CHECK_EQ(packed.entry_scene_identity, directory.entry_scene_identity);
    CHECK_EQ(packed.scenes.size(), directory.scenes.size());
    CHECK_EQ(packed.scene.entity_count(), directory.scene.entity_count());

    packed.destroy();
    directory.destroy();
    blob->back() ^= 0xff;
    try {
        (void)termin::runtime::open_runtime_package_blob(blob, "corrupt-reader-test-blob");
        CHECK(false);
    } catch (const std::exception& exception) {
        CHECK_EQ(std::string(exception.what()), "runtime package blob hash mismatch: scenes/Main.scene.json");
    }
}
