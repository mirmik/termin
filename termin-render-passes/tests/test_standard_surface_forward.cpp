#include "guard_main.h"

GUARD_TEST_MAIN();

#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>

#include <termin/materials/surface_contract_registry.h>
#include <termin/render/color_pass.hpp>
#include <termin/render/material_pipeline.hpp>
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

        tc_shader_contract_view contract{};
        REQUIRE(tc_shader_get_contract_view(variant.get(), &contract));
        REQUIRE(contract_resource(contract, "standard_material") != nullptr);
        REQUIRE(contract_resource(contract, "lighting") != nullptr);
        REQUIRE(contract_resource(contract, "shadow_block") != nullptr);
        REQUIRE(contract_resource(contract, "shadow_maps") != nullptr);
        require_vulkan_compilation(variant);
    }

    tc_surface_contract_registry_clear();
    tc_shader_shutdown();
}
