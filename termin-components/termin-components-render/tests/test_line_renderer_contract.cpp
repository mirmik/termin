#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cstring>
#include <vector>

#include <components/mesh_component.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/line_renderer.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

extern "C" {
#include <core/tc_drawable_protocol.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
}

namespace {

constexpr const char* kVertexSource = R"(
struct VertexOutput { float4 position : SV_Position; };

[shader("vertex")]
VertexOutput vs_main() {
    VertexOutput output;
    output.position = float4(0.0, 0.0, 0.0, 1.0);
    return output;
}
)";

constexpr const char* kFragmentSource = R"(
struct FragmentInput
{
    float4 screen_pos : SV_Position;
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
};

struct FragmentOutput { float4 color : SV_Target0; };

[shader("fragment")]
FragmentOutput fs_main(FragmentInput input)
{
    FragmentOutput output;
    output.color = float4(abs(input.normal_world), 1.0);
    return output;
}
)";

termin::TcShader make_test_material_shader(const char* uuid)
{
    tc_shader_handle handle = tc_shader_from_sources_with_entries_ex(
        kVertexSource,
        kFragmentSource,
        nullptr,
        "LineRendererContractMaterial",
        nullptr,
        uuid,
        TC_SHADER_LANGUAGE_SLANG,
        TC_SHADER_ARTIFACT_OPTIONAL,
        "vs_main",
        "fs_main",
        nullptr);
    return termin::TcShader(handle);
}

termin::MaterialPipelinePassContract line_material_fragment_contract()
{
    termin::MaterialPipelinePassContract contract;
    contract.debug_name = "custom_line_material_fragment";
    contract.required_material_fragment_input =
        termin::material_pipeline_standard_material_fragment_interface();
    contract.uses_material_fragment = true;
    return contract;
}

termin::MaterialPipelinePassContract line_auxiliary_contract()
{
    termin::MaterialPipelinePassContract contract;
    contract.debug_name = "custom_line_auxiliary";
    contract.required_material_fragment_input = termin::MaterialFragmentInterface{};
    contract.uses_material_fragment = true;
    return contract;
}

bool has_variant(
    const std::vector<termin::TcShader>& shaders,
    tc_shader_variant_op variant_op)
{
    for (const termin::TcShader& shader : shaders) {
        if (shader.variant_op() == variant_op) {
            return true;
        }
    }
    return false;
}

termin::TcMesh make_two_submesh_mesh()
{
    const float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
        2.0f, 0.0f, 0.0f,
        3.0f, 0.0f, 0.0f,
        2.0f, 1.0f, 0.0f,
    };
    const uint32_t indices[] = {0, 1, 2, 3, 4, 5};
    auto make_submesh = [](uint32_t first_index, uint32_t index_count, uint32_t material_slot, const char* name) {
        tc_submesh submesh{};
        submesh.first_index = first_index;
        submesh.index_count = index_count;
        submesh.material_slot = material_slot;
        submesh.draw_mode = TC_DRAW_TRIANGLES;
        std::strncpy(submesh.name, name, TC_SUBMESH_NAME_MAX - 1);
        return submesh;
    };
    const std::vector<tc_submesh> submeshes = {
        make_submesh(0, 3, 0, "left"),
        make_submesh(3, 3, 1, "right"),
    };
    tc_vertex_layout layout = tc_vertex_layout_pos();
    termin::TcMeshCreateInfo create_info;
    create_info.data = termin::TcMeshInterleavedDataView{
        vertices,
        6,
        indices,
        6,
        &layout};
    create_info.submeshes = submeshes.data();
    create_info.submesh_count = submeshes.size();
    create_info.name = "mesh-renderer-geometry-ids-test";
    create_info.uuid_hint = "mesh-renderer-geometry-ids-test";
    return termin::TcMesh::from_interleaved(create_info);
}

} // namespace

TEST_CASE("LineRenderer context-aware usage collection follows explicit pass contract") {
    tc_shader_init();

    termin::TcShader material_shader = make_test_material_shader(
        "line-contract-material");
    REQUIRE(material_shader.is_valid());

    termin::LineRenderer renderer;
    renderer.render_mode = termin::LineRenderMode::WorldTube;
    renderer.cast_shadow = true;

    termin::ShaderOverrideContext context;
    context.phase_mark = "actor_attribute";
    context.geometry_id = 0;
    context.original_shader = material_shader;
    context.pass_contract = line_material_fragment_contract();

    std::vector<termin::TcShader> emitted;
    renderer.collect_shader_usages_with_context(
        context,
        [&](termin::TcShader shader) {
            emitted.push_back(shader);
        });

    CHECK(emitted.size() >= 3u);
    CHECK(has_variant(emitted, TC_SHADER_VARIANT_LINE_TUBE_BODY));
    CHECK(has_variant(emitted, TC_SHADER_VARIANT_LINE_TUBE_CAP));

    termin::ShaderOverrideContext auxiliary_context;
    auxiliary_context.phase_mark = "actor_attribute";
    auxiliary_context.geometry_id = 0;
    auxiliary_context.original_shader = material_shader;
    auxiliary_context.pass_contract = line_auxiliary_contract();

    std::vector<termin::TcShader> auxiliary_emitted;
    renderer.collect_shader_usages_with_context(
        auxiliary_context,
        [&](termin::TcShader shader) {
            auxiliary_emitted.push_back(shader);
        });

    CHECK(!has_variant(auxiliary_emitted, TC_SHADER_VARIANT_LINE_TUBE_BODY));
    CHECK(!has_variant(auxiliary_emitted, TC_SHADER_VARIANT_LINE_TUBE_CAP));

    termin::ShaderOverrideContext material_context;
    material_context.phase_mark = "shadow";
    material_context.geometry_id = 0;
    material_context.original_shader = material_shader;
    material_context.pass_contract = line_material_fragment_contract();

    std::vector<termin::TcShader> material_emitted;
    renderer.collect_shader_usages_with_context(
        material_context,
        [&](termin::TcShader shader) {
            material_emitted.push_back(shader);
        });

    CHECK(has_variant(material_emitted, TC_SHADER_VARIANT_LINE_TUBE_BODY));
    CHECK(has_variant(material_emitted, TC_SHADER_VARIANT_LINE_TUBE_CAP));

    tc_shader_shutdown();
}

TEST_CASE("MeshRenderer geometry ids are permissive for pass phase labels") {
    tc_mesh_init();

    termin::TcMesh mesh = make_two_submesh_mesh();
    REQUIRE(mesh.is_valid());

    termin::TcSceneRef scene = termin::TcSceneRef::create("mesh-renderer-geometry-ids");
    termin::Entity entity = scene.create_entity("mesh");

    auto* mesh_component = new termin::MeshComponent();
    mesh_component->set_mesh(mesh);
    entity.add_component(mesh_component);

    auto* renderer = new termin::MeshRenderer();
    entity.add_component(renderer);

    termin::RenderContext context;
    context.phase = "custom_depth";
    void* ids_ptr = tc_component_get_geometry_ids_for_phase(
        renderer->tc_component_ptr(),
        &context,
        "custom_depth");
    REQUIRE(ids_ptr != nullptr);

    auto* ids = static_cast<std::vector<int>*>(ids_ptr);
    REQUIRE(ids->size() == 2u);
    CHECK((*ids)[0] == 0);
    CHECK((*ids)[1] == 1);

    tc_mesh_shutdown();
}
