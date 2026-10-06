#include "guard_main.h"

GUARD_TEST_MAIN();

#include <termin/navmesh/detour_navmesh_asset_utils.hpp>
#include <termin/navmesh/navmesh_keeper_component.hpp>
#include <termin/navmesh/off_mesh_link_component.hpp>
#include <termin/navmesh/recast_navmesh_builder_component.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/tc_scene.hpp>
#include <termin/render/render_task.hpp>
#include <termin/render/vertex_transform_contracts.hpp>
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_shader_registry.h>

#include <cstring>
#include <vector>

namespace {

    template <typename Producer>
    std::vector<tc_material_handle> enumerate_materials(Producer& producer,
                                                       const tc_render_item_collect_context& context) {
        std::vector<tc_material_handle> materials;
        tc_material_sink sink{};
        sink.emit = [](tc_material_handle material, void* user_data) {
            static_cast<std::vector<tc_material_handle>*>(user_data)->push_back(material);
            return true;
        };
        sink.user_data = &materials;
        REQUIRE(producer.collect_materials(context, sink));
        return materials;
    }

    template <typename Producer>
    termin::RenderItemCollection check_materials_match_render_items(
        Producer& producer, const tc_render_item_collect_context& context) {
        const auto materials = enumerate_materials(producer, context);
        termin::RenderItemCollection collection;
        REQUIRE(termin::collect_drawable_render_items(producer.tc_component_ptr(), context, collection));
        REQUIRE_EQ(materials.size(), collection.items.size());
        for (size_t i = 0; i < materials.size(); ++i) {
            CHECK(tc_material_handle_eq(materials[i], collection.items[i].material));
        }
        return collection;
    }

    struct CountingOffMeshLink : termin::OffMeshLinkComponent {
        mutable size_t model_queries = 0;
        termin::Mat44f get_model_matrix(const termin::Entity&) const override {
            ++model_queries;
            return termin::Mat44f::identity();
        }
    };

    bool contract_has_required_input(const tc_shader_contract_view& contract, const char* semantic) {
        for (uint32_t i = 0; i < contract.vertex_input_count; ++i) {
            if (contract.vertex_inputs[i].required && std::strcmp(contract.vertex_inputs[i].semantic, semantic) == 0) {
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
    color_contract.allows_authored_vertex_stage = true;
    color_contract.required_material_fragment_input = termin::material_pipeline_standard_material_fragment_interface();
    color_contract.vertex_output_adapter = termin::material_pipeline_standard_material_vertex_output_adapter();
    color_contract.static_vertex_transform = termin::material_pipeline_make_static_mesh_vertex_transform_provider(
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
    const termin::RenderItemTaskPlanningResult result = termin::plan_render_item_task(request, tasks);
    REQUIRE(result.accepted());
    REQUIRE_EQ(tasks.size(), 1u);
    CHECK(tc_shader_handle_eq(tasks.at(result.task_index).final_shader, phase->shader));

    tc_mesh_shutdown();
    tc_material_shutdown();
    tc_shader_shutdown();
}

TEST_CASE("OffMeshLink material enumeration consumes prepared geometry without refreshing payloads") {
    tc_shader_init();
    tc_material_init();
    tc_mesh_init();
    {
        CountingOffMeshLink link;
        tc_render_item_collect_context context{};
        context.phase = TC_PHASE_ID;
        context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
        CHECK(enumerate_materials(link, context).empty());
        link.prepare_render(termin::RenderPrepareContext(TC_SCENE_HANDLE_INVALID));
        auto materials = enumerate_materials(link, context);
        REQUIRE_EQ(materials.size(), 1u);
        CHECK_EQ(link.model_queries, 0u);
        auto items = check_materials_match_render_items(link, context);
        REQUIRE_EQ(items.items.size(), 1u);
        tc_mesh* mesh = tc_mesh_get(items.items[0].payload.mesh.mesh_handle);
        REQUIRE(mesh != nullptr);
        const uint32_t version = mesh->header.version;
        link.end_local = {2.0, 3.0, 4.0};
        materials = enumerate_materials(link, context);
        REQUIRE_EQ(materials.size(), 1u);
        CHECK_EQ(mesh->header.version, version);
        CHECK_EQ(link.model_queries, 1u);
        link.prepare_render(termin::RenderPrepareContext(TC_SCENE_HANDLE_INVALID));
        CHECK(mesh->header.version > version);
        const uint32_t refreshed_version = mesh->header.version;
        link.prepare_render(termin::RenderPrepareContext(TC_SCENE_HANDLE_INVALID));
        CHECK_EQ(mesh->header.version, refreshed_version);
        link.enabled = false;
        check_materials_match_render_items(link, context);
        context.phase = TC_PHASE_OPAQUE;
        CHECK(enumerate_materials(link, context).empty());
        check_materials_match_render_items(link, context);
        context.phase = TC_PHASE_EDITOR_DEBUG;
        context.render_category_mask = 0;
        CHECK(enumerate_materials(link, context).empty());
        check_materials_match_render_items(link, context);
    }
    tc_mesh_shutdown();
    tc_material_shutdown();
    tc_shader_shutdown();
}

TEST_CASE("Empty native navmesh producers enumerate no dependencies") {
    tc_shader_init();
    tc_material_init();
    tc_mesh_init();
    {
        termin::NavMeshKeeperComponent keeper;
        termin::RecastNavMeshBuilderComponent builder;
        tc_render_item_collect_context context{};
        context.phase = TC_PHASE_EDITOR_DEBUG;
        context.render_category_mask = TC_RENDER_CATEGORY_NAVMESH;
        keeper.prepare_render(termin::RenderPrepareContext(TC_SCENE_HANDLE_INVALID));
        CHECK(enumerate_materials(keeper, context).empty());
        check_materials_match_render_items(keeper, context);
        builder.show_input_mesh = true;
        CHECK(enumerate_materials(builder, context).empty());
        check_materials_match_render_items(builder, context);
    }
    tc_mesh_shutdown();
    tc_material_shutdown();
    tc_shader_shutdown();
}
