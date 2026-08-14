#include "guard_main.h"

GUARD_TEST_MAIN();

#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>

#include <termin/lighting/lighting_ubo.hpp>
#include <termin/materials/surface_contract_registry.h>
#include <termin/render/color_pass.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/render/standard_gbuffer_pass.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

namespace {

    constexpr const char* STANDARD_EVALUATOR = R"slang(
struct FragmentInput {
    float4 screen_pos : SV_Position;
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
    float2 uv : TEXCOORD2;
    float3 tangent_world : TEXCOORD3;
    float3 bitangent_world : TEXCOORD4;
    float tbn_valid : TEXCOORD5;
};

struct TestStandardMaterial {
    float4 base_color;
    float metallic;
    float roughness;
    float occlusion;
    float emission;
};

[[TerminScope("material")]]
ConstantBuffer<TestStandardMaterial> standard_material;

TerminStandardSurfaceV1 evaluate_standard_surface(FragmentInput input) {
    TerminStandardSurfaceV1 surface;
    surface.base_color = standard_material.base_color.rgb;
    surface.normal_world = normalize(input.normal_world);
    surface.metallic = saturate(standard_material.metallic);
    surface.perceptual_roughness = saturate(standard_material.roughness);
    surface.occlusion = saturate(standard_material.occlusion);
    surface.emission =
        standard_material.base_color.rgb * standard_material.emission;
    surface.opacity = saturate(standard_material.base_color.a);
    return surface;
}
)slang";

    struct ScopedArtifactConfiguration {
        std::filesystem::path root;

        ScopedArtifactConfiguration() {
            const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
            root =
                std::filesystem::temp_directory_path() / ("termin-standard-surface-forward-" + std::to_string(unique));
            std::filesystem::remove_all(root);
            termin::tgfx2_set_shader_artifact_root(root.string().c_str());
            termin::tgfx2_set_shader_cache_root("");
#ifdef TERMIN_STANDARD_SURFACE_FORWARD_TEST_SHADERC
            termin::tgfx2_set_shader_compiler_path(TERMIN_STANDARD_SURFACE_FORWARD_TEST_SHADERC);
#endif
            termin::tgfx2_set_shader_dev_compile_enabled(true);
        }

        ~ScopedArtifactConfiguration() {
            termin::tgfx2_set_shader_dev_compile_enabled(false);
            termin::tgfx2_set_shader_compiler_path("");
            termin::tgfx2_set_shader_cache_root("");
            termin::tgfx2_set_shader_artifact_root("");
            std::filesystem::remove_all(root);
        }
    };

    const tc_shader_resource_requirement* contract_resource(const tc_shader_contract_view& contract, const char* name) {
        for (uint32_t index = 0; index < contract.resource_count; ++index) {
            if (std::strcmp(contract.resources[index].name, name) == 0) {
                return &contract.resources[index];
            }
        }
        return nullptr;
    }

    termin::TcShader make_standard_surface_producer() {
        const char* semantics[] = {
            "world_pos",
            "normal_world",
            "uv",
            "tangent_world",
            "bitangent_world",
            "tbn_valid",
        };
        const uint32_t types[] = {
            TC_SHADER_CONTRACT_VALUE_FLOAT3,
            TC_SHADER_CONTRACT_VALUE_FLOAT3,
            TC_SHADER_CONTRACT_VALUE_FLOAT2,
            TC_SHADER_CONTRACT_VALUE_FLOAT3,
            TC_SHADER_CONTRACT_VALUE_FLOAT3,
            TC_SHADER_CONTRACT_VALUE_FLOAT,
        };
        tc_shader_fragment_input inputs[6]{};
        for (uint32_t index = 0; index < 6u; ++index) {
            std::snprintf(inputs[index].semantic, sizeof(inputs[index].semantic), "%s", semantics[index]);
            inputs[index].type = types[index];
        }

        tc_shader_resource_requirement resources[1]{};
        std::snprintf(resources[0].name, sizeof(resources[0].name), "%s", "standard_material");
        resources[0].kind = TC_SHADER_RESOURCE_CONSTANT_BUFFER;
        resources[0].scope = TC_SHADER_RESOURCE_SCOPE_MATERIAL;
        resources[0].stage_mask = TC_SHADER_STAGE_FRAGMENT;
        resources[0].size = 32u;

        const tc_shader_surface_producer_desc producer = {
            TC_SHADER_SURFACE_PRODUCER_SCHEMA_VERSION,
            TC_STANDARD_PBR_SURFACE_CONTRACT_ID,
            TC_STANDARD_PBR_SURFACE_CONTRACT_VERSION,
            "TerminStandardSurfaceV1",
            "evaluate_standard_surface",
            STANDARD_EVALUATOR,
            "termin.surface.standard-pbr@1:test-evaluator:v1",
            inputs,
            6u,
            resources,
            1u,
        };

        termin::TcShaderCreateInfo create_info{};
        create_info.sources.fragment = STANDARD_EVALUATOR;
        create_info.sources.name = "StandardSurfaceForwardTestProducer";
        create_info.sources.fragment_entry = "evaluate_standard_surface";
        create_info.uuid = "termin-standard-surface-forward-test-producer";
        create_info.language = TC_SHADER_LANGUAGE_SLANG;
        create_info.artifact_policy = TC_SHADER_ARTIFACT_REQUIRED;
        create_info.surface_producer = &producer;
        return termin::TcShader::from_sources(create_info);
    }

    termin::TcShader make_final_color_shader() {
        constexpr const char* source = R"slang(
struct VertexInput { float3 position : POSITION; };
struct VertexOutput { float4 position : SV_Position; };
[shader("vertex")]
VertexOutput vs_main(VertexInput input) {
    VertexOutput output;
    output.position = float4(input.position, 1.0);
    return output;
}
[shader("fragment")]
float4 fs_main() : SV_Target0 { return float4(1.0, 0.0, 0.0, 1.0); }
)slang";
        termin::TcShaderCreateInfo create_info{};
        create_info.sources.vertex = source;
        create_info.sources.fragment = source;
        create_info.sources.name = "FinalColorRoutingTest";
        create_info.sources.vertex_entry = "vs_main";
        create_info.sources.fragment_entry = "fs_main";
        create_info.uuid = "termin-final-color-routing-test";
        create_info.language = TC_SHADER_LANGUAGE_SLANG;
        return termin::TcShader::from_sources(create_info);
    }

    termin::TcShader make_surface_routing_probe(const char* contract_id,
                                                uint32_t contract_version,
                                                const char* surface_type,
                                                const char* uuid) {
        const tc_shader_surface_producer_desc producer = {
            TC_SHADER_SURFACE_PRODUCER_SCHEMA_VERSION,
            contract_id,
            contract_version,
            surface_type,
            "evaluate_standard_surface",
            STANDARD_EVALUATOR,
            uuid,
            nullptr,
            0u,
            nullptr,
            0u,
        };
        termin::TcShaderCreateInfo create_info{};
        create_info.sources.fragment = STANDARD_EVALUATOR;
        create_info.sources.name = "SurfaceRoutingProbe";
        create_info.sources.fragment_entry = "evaluate_standard_surface";
        create_info.uuid = uuid;
        create_info.language = TC_SHADER_LANGUAGE_SLANG;
        create_info.surface_producer = &producer;
        return termin::TcShader::from_sources(create_info);
    }

    void require_vulkan_compilation(const termin::TcShader& shader) {
        std::vector<uint8_t> vertex_artifact;
        std::vector<uint8_t> fragment_artifact;
        REQUIRE(termin::tgfx2_load_or_compile_shader_artifact_for_backend(
            shader.get(), tgfx::BackendType::Vulkan, tgfx::ShaderStage::Vertex, vertex_artifact));
        REQUIRE_FALSE(vertex_artifact.empty());
        REQUIRE(termin::tgfx2_load_or_compile_shader_artifact_for_backend(
            shader.get(), tgfx::BackendType::Vulkan, tgfx::ShaderStage::Fragment, fragment_artifact));
        REQUIRE_FALSE(fragment_artifact.empty());
    }

} // namespace

TEST_CASE("standard forward consumer composes static skinned and foliage variants") {
    tc_shader_init();
    tc_surface_contract_registry_clear();
    REQUIRE(tc_surface_contract_registry_register_builtins());

    termin::TcShader producer = make_standard_surface_producer();
    REQUIRE(producer.is_valid());
    REQUIRE(producer.has_surface_producer());

    const termin::MaterialPipelinePassContract pass = termin::color_material_pass_contract();
    REQUIRE(pass.fragment_composition == termin::MaterialFragmentComposition::SurfaceConsumerOrFinalColor);
    REQUIRE(pass.surface_consumer.has_value());

    const termin::VertexTransformKind transforms[] = {
        termin::VertexTransformKind::StaticMesh,
        termin::VertexTransformKind::SkinnedMesh,
        termin::VertexTransformKind::Foliage,
    };
    ScopedArtifactConfiguration artifacts;
    for (termin::VertexTransformKind transform : transforms) {
        termin::MaterialShaderOverrideRequest request{};
        request.original_shader = producer;
        request.vertex_transform_kind = transform;
        request.pass_contract = pass;
        request.debug_context = "standard-surface-forward-test";
        termin::TcShader variant = termin::assemble_material_shader_override(request);
        REQUIRE(variant.is_valid());
        REQUIRE(variant.is_executable());
        CHECK(std::strstr(variant.fragment_source(), "evaluate_standard_surface") != nullptr);
        CHECK(std::strstr(variant.fragment_source(), "termin_standard_pbr_forward") != nullptr);
        CHECK(std::strstr(variant.fragment_source(), "has_environment_lighting()") != nullptr);

        tc_shader_contract_view contract{};
        REQUIRE(tc_shader_get_contract_view(variant.get(), &contract));
        REQUIRE(contract_resource(contract, "standard_material") != nullptr);
        REQUIRE(contract_resource(contract, "lighting") != nullptr);
        REQUIRE(contract_resource(contract, "shadow_block") != nullptr);
        REQUIRE(contract_resource(contract, "shadow_maps") != nullptr);
        REQUIRE(contract_resource(contract, "ibl_diffuse_irradiance") != nullptr);
        REQUIRE(contract_resource(contract, "ibl_prefiltered_specular") != nullptr);
        REQUIRE(contract_resource(contract, "ibl_brdf_lut") != nullptr);
        require_vulkan_compilation(variant);
    }

    tc_surface_contract_registry_clear();
    tc_shader_shutdown();
}

TEST_CASE("lighting UBO explicitly distinguishes ambient fallback from environment lighting") {
    termin::LightingUBO lighting;
    const termin::Vec3 ambient{0.2, 0.3, 0.4};
    const termin::Vec3 camera{1.0, 2.0, 3.0};
    const termin::ShadowSettings shadows{};

    lighting.update_from_lights({}, ambient, 0.75f, camera, shadows, false);
    CHECK(lighting.data.environment_lighting_enabled == 0.0f);
    CHECK(lighting.data.ambient_color.x == guard::Approx(0.2).epsilon(1e-6));
    CHECK(lighting.data.ambient_color.y == guard::Approx(0.3).epsilon(1e-6));
    CHECK(lighting.data.ambient_color.z == guard::Approx(0.4).epsilon(1e-6));
    CHECK(lighting.data.ambient_intensity == guard::Approx(0.75));

    lighting.update_from_lights({}, ambient, 0.75f, camera, shadows, true);
    CHECK(lighting.data.environment_lighting_enabled == 1.0f);
}

TEST_CASE("standard G-buffer consumer composes static skinned and foliage variants") {
    tc_shader_init();
    tc_surface_contract_registry_clear();
    REQUIRE(tc_surface_contract_registry_register_builtins());

    termin::TcShader producer = make_standard_surface_producer();
    REQUIRE(producer.is_valid());

    const termin::MaterialPipelinePassContract pass = termin::standard_gbuffer_material_pass_contract();
    REQUIRE(pass.fragment_composition == termin::MaterialFragmentComposition::SurfaceConsumer);
    REQUIRE(pass.surface_consumer.has_value());
    CHECK(pass.surface_consumer->resources.empty());
    CHECK(termin::material_pipeline_pass_accepts_shader(pass, producer));
    CHECK_FALSE(termin::material_pipeline_pass_accepts_shader(pass, make_final_color_shader()));
    const termin::TcShader foreign =
        make_surface_routing_probe("game.surface.foreign", 1u, "GameSurface", "foreign-surface-routing-probe");
    CHECK_FALSE(termin::material_pipeline_pass_accepts_shader(pass, foreign));
    const termin::TcShader malformed_compatible =
        make_surface_routing_probe(TC_STANDARD_PBR_SURFACE_CONTRACT_ID,
                                   TC_STANDARD_PBR_SURFACE_CONTRACT_VERSION,
                                   "WrongStandardSurfaceType",
                                   "malformed-standard-surface-routing-probe");
    CHECK(termin::material_pipeline_pass_accepts_shader(pass, malformed_compatible));
    termin::MaterialShaderOverrideRequest malformed_request{};
    malformed_request.original_shader = malformed_compatible;
    malformed_request.vertex_transform_kind = termin::VertexTransformKind::StaticMesh;
    malformed_request.pass_contract = pass;
    malformed_request.debug_context = "standard-gbuffer-malformed-compatible-test";
    CHECK_FALSE(termin::assemble_material_shader_override(malformed_request).is_valid());

    const termin::VertexTransformKind transforms[] = {
        termin::VertexTransformKind::StaticMesh,
        termin::VertexTransformKind::SkinnedMesh,
        termin::VertexTransformKind::Foliage,
    };
    ScopedArtifactConfiguration artifacts;
    for (termin::VertexTransformKind transform : transforms) {
        termin::MaterialShaderOverrideRequest request{};
        request.original_shader = producer;
        request.vertex_transform_kind = transform;
        request.pass_contract = pass;
        request.debug_context = "standard-gbuffer-test";
        termin::TcShader variant = termin::assemble_material_shader_override(request);
        REQUIRE(variant.is_valid());
        REQUIRE(variant.is_executable());
        CHECK(std::strstr(variant.fragment_source(), "termin_standard_gbuffer_fs") != nullptr);
        CHECK(std::strstr(variant.fragment_source(), "SV_Target0") != nullptr);
        CHECK(std::strstr(variant.fragment_source(), "SV_Target1") != nullptr);
        CHECK(std::strstr(variant.fragment_source(), "SV_Target2") != nullptr);

        tc_shader_contract_view contract{};
        REQUIRE(tc_shader_get_contract_view(variant.get(), &contract));
        REQUIRE(contract_resource(contract, "standard_material") != nullptr);
        CHECK(contract_resource(contract, "lighting") == nullptr);
        CHECK(contract_resource(contract, "shadow_block") == nullptr);
        CHECK(contract_resource(contract, "shadow_maps") == nullptr);
        CHECK(contract_resource(contract, "ibl_diffuse_irradiance") == nullptr);
        CHECK(contract_resource(contract, "ibl_prefiltered_specular") == nullptr);
        CHECK(contract_resource(contract, "ibl_brdf_lut") == nullptr);
        require_vulkan_compilation(variant);
    }

    tc_surface_contract_registry_clear();
    tc_shader_shutdown();
}

TEST_CASE("standard G-buffer pass publishes independent high precision planes and depth") {
    const termin::StandardGBufferPass pass;
    const std::vector<termin::ResourceSpec> specs = pass.get_resource_specs();
    REQUIRE(specs.size() == 4);
    CHECK(specs[0].resource == "gbuffer_base_ao");
    CHECK(specs[1].resource == "gbuffer_normal_rough");
    CHECK(specs[2].resource == "gbuffer_metal_emit");
    CHECK(specs[3].resource == "scene_depth");
    for (size_t index = 0; index < 3; ++index) {
        CHECK(specs[index].resource_type == "color_texture");
        REQUIRE(specs[index].format.has_value());
        CHECK(*specs[index].format == "rgba16f");
        CHECK(specs[index].samples == 1);
    }
    CHECK(specs[3].resource_type == "depth_texture");
    REQUIRE(specs[3].format.has_value());
    CHECK(*specs[3].format == "depth32f");
    CHECK(specs[3].samples == 1);

    CHECK(pass.compute_reads().empty());
    const std::set<const char*> writes = pass.compute_writes();
    CHECK(writes.size() == 4);
}
