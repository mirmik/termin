#include "guard_main.h"

GUARD_TEST_MAIN();

#include <termin/navmesh/detour_navmesh_asset_utils.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/render/render_task.hpp>
#include <termin/render/vertex_transform_contracts.hpp>
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_shader_registry.h>

#include <cstring>

namespace {

bool contract_has_required_input(const tc_shader_contract_view& contract, const char* semantic) {
    for (uint32_t i = 0; i < contract.vertex_input_count; ++i) {
        if (contract.vertex_inputs[i].required &&
            std::strcmp(contract.vertex_inputs[i].semantic, semantic) == 0) {
            return true;
        }
    }
    return false;
}

} // namespace

TEST_CASE("navmesh debug shader publishes its authored vertex interface") {
    tc_shader_init();
    tc_material_init();
    tc_mesh_init();

    termin::TcMaterial material;
    material = termin::get_or_create_navmesh_debug_material(material);
    REQUIRE(material.is_valid());
    tc_material_phase* phase = material.find_phase(termin::NAVMESH_DEBUG_PHASE);
    REQUIRE(phase != nullptr);

    tc_shader* shader = tc_shader_get(phase->shader);
    REQUIRE(shader != nullptr);
    tc_shader_contract_view shader_contract_view{};
    REQUIRE(tc_shader_get_contract_view(shader, &shader_contract_view));
    CHECK(contract_has_required_input(shader_contract_view, "position"));
    CHECK(contract_has_required_input(shader_contract_view, "color"));
    CHECK_FALSE(contract_has_required_input(shader_contract_view, "normal"));
    CHECK_FALSE(contract_has_required_input(shader_contract_view, "uv"));
    CHECK_FALSE(contract_has_required_input(shader_contract_view, "tangent"));

    tc_vertex_layout layout{};
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 1);
    const tc_mesh_handle mesh_handle = tc_mesh_create("navmesh-debug-shader-contract-test-mesh");
    REQUIRE(!tc_mesh_handle_is_invalid(mesh_handle));
    tc_mesh* mesh = tc_mesh_get(mesh_handle);
    REQUIRE(mesh != nullptr);
    mesh->layout = layout;

    tc_render_item item{};
    item.kind = TC_RENDER_ITEM_KIND_MESH;
    item.flags = TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX | TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE;
    item.material = material.handle;
    item.material_phase = phase;
    item.material_phase_index = 0;
    item.payload.mesh.mesh_handle = mesh_handle;

    termin::MaterialPipelinePassContract color_contract{};
    color_contract.debug_name = "color";
    color_contract.required_material_fragment_input =
        termin::material_pipeline_standard_material_fragment_interface();
    color_contract.uses_material_fragment = true;
    color_contract.vertex_output_adapter =
        termin::material_pipeline_standard_material_vertex_output_adapter();
    color_contract.static_vertex_transform =
        termin::material_pipeline_make_static_mesh_vertex_transform_provider(
            "static", termin::MeshVertexTransformProfile::Material, "draw_data.u_model");

    termin::RenderItemTaskPlanningContract planning_contract{};
    planning_contract.phase = TC_PHASE_EDITOR_DEBUG;
    planning_contract.material_phase_policy = termin::RenderItemMaterialPhasePolicy::Required;
    planning_contract.provided_input_mask =
        termin::render_item_task_input_bit(termin::RenderItemTaskInput::DrawContext);
    planning_contract.required_input_mask =
        termin::render_item_task_input_bit(termin::RenderItemTaskInput::DrawContext);
    planning_contract.accepted_vertex_transform_kind_mask =
        termin::render_item_vertex_transform_kind_bit(termin::VertexTransformKind::StaticMesh);
    planning_contract.shader_contract = &color_contract;
    planning_contract.debug_pass_name = "EditorDebug";

    termin::RenderItemTaskPlanningRequest request{};
    request.item = &item;
    request.material_phase = phase;
    request.candidate_shader = phase->shader;
    request.contract = &planning_contract;

    termin::RenderTaskList tasks;
    const termin::RenderItemTaskPlanningResult result =
        termin::plan_render_item_task(request, tasks);
    REQUIRE(result.accepted());
    REQUIRE_EQ(tasks.size(), 1u);
    CHECK(tc_shader_handle_eq(tasks.at(result.task_index).final_shader, phase->shader));

    tc_mesh_shutdown();
    tc_material_shutdown();
    tc_shader_shutdown();
}
