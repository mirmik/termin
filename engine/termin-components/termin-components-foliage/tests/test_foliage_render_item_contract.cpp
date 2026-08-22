#include "guard_main.h"

GUARD_TEST_MAIN();

#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <system_error>
#include <vector>

#include <termin/foliage/foliage_data_registry.hpp>
#include <termin/foliage/foliage_file.hpp>
#include <termin/foliage/foliage_layer_component.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/render_task.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

extern "C" {
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
}

namespace {

    struct ScopedTempFile {
        std::filesystem::path path;

        ~ScopedTempFile() {
            std::error_code ignored;
            std::filesystem::remove(path, ignored);
        }
    };

    ScopedTempFile foliage_temp_file(const char* label) {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        return {std::filesystem::temp_directory_path() /
                (std::string("termin-foliage-") + label + "-" + std::to_string(unique) + ".tfoliage")};
    }

    termin::TcMesh make_test_mesh() {
        const float vertices[] = {
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 1.0f,
        };
        const uint32_t indices[] = {0, 1, 2};
        tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv();

        termin::TcMeshCreateInfo create_info;
        create_info.data = termin::TcMeshInterleavedDataView{vertices, 3, indices, 3, &layout};
        create_info.name = "foliage-render-item-test-mesh";
        create_info.uuid_hint = "foliage-render-item-test-mesh";
        return termin::TcMesh::from_interleaved(create_info);
    }

} // namespace

TEST_CASE("FoliageData keeps canonical bounds separate from empty state") {
    termin::FoliageData data;
    CHECK_FALSE(data.has_local_bounds);
    CHECK(data.local_bounds.is_valid());

    data.add_instance(termin::FoliageInstance{.px = 2.0f, .py = -3.0f, .pz = 5.0f});
    data.add_instance(termin::FoliageInstance{.px = -4.0f, .py = 7.0f, .pz = 1.0f});
    REQUIRE(data.has_local_bounds);
    CHECK(data.local_bounds.min_point == (termin::Vec3f{-4.0f, -3.0f, 1.0f}));
    CHECK(data.local_bounds.max_point == (termin::Vec3f{2.0f, 7.0f, 5.0f}));

    CHECK_EQ(data.remove_instances_in_radius({2.0f, -3.0f, 5.0f}, 0.0f), 1u);
    REQUIRE(data.has_local_bounds);
    CHECK(data.local_bounds.min_point == (termin::Vec3f{-4.0f, 7.0f, 1.0f}));
    CHECK(data.local_bounds.max_point == data.local_bounds.min_point);

    data.clear();
    CHECK_FALSE(data.has_local_bounds);
    CHECK(data.local_bounds.is_valid());
}

TEST_CASE("FoliageData rejects non-finite instance geometry transactionally") {
    termin::FoliageData data;
    const uint32_t initial_version = data.version;

    termin::FoliageInstance invalid;
    invalid.px = std::numeric_limits<float>::quiet_NaN();
    CHECK_FALSE(data.add_instance(invalid));
    CHECK(data.instances.empty());
    CHECK_FALSE(data.has_local_bounds);
    CHECK_EQ(data.version, initial_version);

    CHECK_FALSE(data.set_instances({termin::FoliageInstance{.px = 1.0f}, invalid}));
    CHECK(data.instances.empty());
    CHECK_FALSE(data.has_local_bounds);
    CHECK_EQ(data.version, initial_version);
}

TEST_CASE("Foliage file round-trips canonical non-empty and empty bounds") {
    const ScopedTempFile populated_file = foliage_temp_file("populated");
    termin::FoliageData source;
    REQUIRE(source.set_instances({
        termin::FoliageInstance{.px = -4.0f, .py = 2.0f, .pz = 8.0f},
        termin::FoliageInstance{.px = 3.0f, .py = -5.0f, .pz = 1.0f},
    }));
    REQUIRE(source.save_to_file(populated_file.path));

    termin::FoliageData loaded;
    REQUIRE(loaded.load_from_file(populated_file.path));
    REQUIRE(loaded.has_local_bounds);
    CHECK_EQ(loaded.instances.size(), 2u);
    CHECK(loaded.local_bounds.min_point == (termin::Vec3f{-4.0f, -5.0f, 1.0f}));
    CHECK(loaded.local_bounds.max_point == (termin::Vec3f{3.0f, 2.0f, 8.0f}));

    const ScopedTempFile empty_file = foliage_temp_file("empty");
    source.clear();
    REQUIRE(source.save_to_file(empty_file.path));
    REQUIRE(loaded.load_from_file(empty_file.path));
    CHECK(loaded.instances.empty());
    CHECK_FALSE(loaded.has_local_bounds);
    CHECK(loaded.local_bounds.min_point == termin::Vec3f{});
    CHECK(loaded.local_bounds.max_point == termin::Vec3f{});
}

TEST_CASE("Foliage loader rejects invalid serialized bounds without mutating output") {
    const ScopedTempFile file = foliage_temp_file("invalid-bounds");
    termin::FoliageData source;
    REQUIRE(source.add_instance(termin::FoliageInstance{.px = 1.0f, .py = 2.0f, .pz = 3.0f}));
    REQUIRE(source.save_to_file(file.path));

    std::fstream stream(file.path, std::ios::binary | std::ios::in | std::ios::out);
    REQUIRE(stream.good());
    stream.seekp(40);
    const float invalid_min = std::numeric_limits<float>::quiet_NaN();
    stream.write(reinterpret_cast<const char*>(&invalid_min), sizeof(invalid_min));
    stream.close();

    termin::FoliageData destination;
    REQUIRE(destination.add_instance(termin::FoliageInstance{.px = 9.0f, .py = 8.0f, .pz = 7.0f}));
    const uint32_t previous_version = destination.version;
    CHECK_FALSE(destination.load_from_file(file.path));
    CHECK_EQ(destination.instances.size(), 1u);
    CHECK(destination.instances.front().position() == (termin::Vec3f{9.0f, 8.0f, 7.0f}));
    CHECK_EQ(destination.version, previous_version);
}

TEST_CASE("Foliage loader rejects a truncated instance block before mutating output") {
    const ScopedTempFile file = foliage_temp_file("truncated-instances");
    termin::FoliageData source;
    REQUIRE(source.save_to_file(file.path));

    std::fstream stream(file.path, std::ios::binary | std::ios::in | std::ios::out);
    REQUIRE(stream.good());
    constexpr std::streamoff instance_count_offset = 32;
    constexpr uint64_t oversized_instance_count = 1'000'000;
    stream.seekp(instance_count_offset);
    stream.write(reinterpret_cast<const char*>(&oversized_instance_count), sizeof(oversized_instance_count));
    stream.close();

    termin::FoliageData destination;
    REQUIRE(destination.add_instance(termin::FoliageInstance{.px = 9.0f, .py = 8.0f, .pz = 7.0f}));
    const uint32_t previous_version = destination.version;

    const termin::FoliageFileResult result = termin::load_foliage_file(file.path, destination);

    CHECK_FALSE(result.ok);
    CHECK(result.message.find("truncated") != std::string::npos);
    CHECK_EQ(destination.instances.size(), 1u);
    CHECK(destination.instances.front().position() == (termin::Vec3f{9.0f, 8.0f, 7.0f}));
    CHECK_EQ(destination.version, previous_version);
}

TEST_CASE("FoliageLayerComponent emits foliage batch render items with owned asset id") {
    tc_material_init();
    tc_mesh_init();
    termin::TcFoliageData::clear_registry_for_tests();
    termin::FoliageLayerComponent::register_type();

    termin::TcFoliageData foliage =
        termin::TcFoliageData::declare("foliage-render-item-test-asset", "foliage-render-item-test-asset");
    REQUIRE(foliage.is_valid());
    REQUIRE(foliage.get() != nullptr);
    foliage.get()->loaded = true;
    foliage.get()->set_instances({
        termin::FoliageInstance{
            .px = 1.0f,
            .py = 2.0f,
            .pz = 3.0f,
            .nx = 0.0f,
            .ny = 0.0f,
            .nz = 1.0f,
            .yaw = 0.25f,
            .scale = 1.0f,
            .variant = 0,
            .seed = 7,
        },
    });

    termin::TcMesh mesh = make_test_mesh();
    REQUIRE(mesh.is_valid());

    tc_material_handle material_handle =
        tc_material_create("foliage-render-item-test-material", "foliage-render-item-test-material");
    REQUIRE(tc_material_is_valid(material_handle));
    tc_material* material = tc_material_get(material_handle);
    REQUIRE(material != nullptr);
    tc_material_phase* phase = tc_material_add_phase(material, tc_shader_handle_invalid(), "opaque", 3);
    REQUIRE(phase != nullptr);

    termin::TcSceneRef scene = termin::TcSceneRef::create("foliage-render-item-test-scene");
    termin::Entity entity = scene.create_entity("foliage");
    auto* layer = new termin::FoliageLayerComponent();
    layer->foliage_uuid = foliage.uuid();
    layer->prototype_mesh = mesh;
    layer->material = termin::TcMaterial(material_handle);
    entity.add_component(layer);

    CHECK(tc_phase_mask_contains(layer->get_phase_mask(), TC_PHASE_OPAQUE));
    CHECK(tc_phase_mask_contains(layer->get_phase_mask(), TC_PHASE_DEPTH));
    CHECK(tc_phase_mask_contains(layer->get_phase_mask(), TC_PHASE_ID));
    CHECK(tc_phase_mask_contains(layer->get_phase_mask(), TC_PHASE_NORMAL));

    termin::RenderItemEncoderCapabilities capabilities{};
    REQUIRE(termin::get_render_item_encoder_capabilities(TC_RENDER_ITEM_KIND_FOLIAGE_BATCH, capabilities));
    CHECK(tc_phase_mask_contains(capabilities.phase_mask, TC_PHASE_ID));
    CHECK(tc_phase_mask_contains(capabilities.phase_mask, TC_PHASE_DEPTH));
    CHECK(tc_phase_mask_contains(capabilities.phase_mask, TC_PHASE_NORMAL));

    tc_render_item_collect_context collect_context{};
    collect_context.phase = TC_PHASE_OPAQUE;
    collect_context.debug_pass_name = "ColorPass";

    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(layer->tc_component_ptr(), collect_context, collection));

    REQUIRE(collection.items.size() == 1u);
    const tc_render_item& item = collection.items[0];
    CHECK(item.kind == TC_RENDER_ITEM_KIND_FOLIAGE_BATCH);
    CHECK(termin::render_scene_item_component(item) == layer->tc_component_ptr());
    CHECK(item.geometry_id == 0);
    CHECK(item.material_phase == phase);
    CHECK((item.flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) != 0u);
    CHECK((item.flags & TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE) != 0u);
    CHECK(tc_mesh_handle_eq(item.payload.foliage_batch.prototype_mesh_handle, mesh.handle));
    REQUIRE(item.payload.foliage_batch.foliage_uuid != nullptr);
    CHECK(std::strcmp(item.payload.foliage_batch.foliage_uuid, "foliage-render-item-test-asset") == 0);

    for (size_t i = 0; i < 64; ++i) {
        REQUIRE(!tc_mesh_handle_is_invalid(tc_mesh_create(nullptr)));
    }
    REQUIRE(tc_mesh_get(item.payload.foliage_batch.prototype_mesh_handle) != nullptr);

    termin::MaterialPipelinePassContract shader_contract{};
    shader_contract.foliage_vertex_transform = termin::material_pipeline_make_foliage_vertex_transform_provider(
        "foliage_handle_relocation_test", termin::MeshVertexTransformProfile::Position);
    shader_contract.foliage_vertex_transform->vertex_inputs.mesh_attributes.push_back(
        {"relocation_probe", termin::MaterialPipelineValueType::Float});
    termin::RenderItemTaskPlanningContract planning_contract{};
    planning_contract.phase = TC_PHASE_OPAQUE;
    planning_contract.provided_input_mask =
        termin::render_item_task_input_bit(termin::RenderItemTaskInput::DrawContext);
    planning_contract.shader_contract = &shader_contract;
    planning_contract.debug_pass_name = "FoliageHandleRelocationPass";

    termin::RenderItemTaskPlanningRequest planning_request{};
    planning_request.item = &item;
    planning_request.contract = &planning_contract;

    termin::RenderTaskList relocated_tasks;
    const termin::RenderItemTaskPlanningResult relocated_result =
        termin::plan_render_item_task(planning_request, relocated_tasks);
    CHECK(relocated_result.rejection == termin::RenderItemTaskRejection::ShaderPlanningRejected);
    REQUIRE(relocated_result.detail != nullptr);
    CHECK(std::strcmp(relocated_result.detail, "prototype mesh does not satisfy the foliage vertex input ABI") == 0);
    CHECK(relocated_tasks.empty());

    tc_render_item stale_item = item;
    const tc_mesh_handle stale_handle = tc_mesh_create("foliage-render-item-stale-handle-test");
    REQUIRE(!tc_mesh_handle_is_invalid(stale_handle));
    stale_item.payload.foliage_batch.prototype_mesh_handle = stale_handle;
    REQUIRE(tc_mesh_destroy(stale_handle));
    planning_request.item = &stale_item;

    termin::RenderTaskList stale_tasks;
    const termin::RenderItemTaskPlanningResult stale_result =
        termin::plan_render_item_task(planning_request, stale_tasks);
    CHECK(stale_result.rejection == termin::RenderItemTaskRejection::ShaderPlanningRejected);
    REQUIRE(stale_result.detail != nullptr);
    CHECK(std::strcmp(stale_result.detail, "foliage prototype mesh handle is stale or invalid") == 0);
    CHECK(stale_tasks.empty());

    tc_render_item_collect_context id_context{};
    id_context.phase = TC_PHASE_ID;
    id_context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
    id_context.debug_pass_name = "IdPass";
    termin::RenderItemCollection id_collection;
    REQUIRE(termin::collect_drawable_render_items(layer->tc_component_ptr(), id_context, id_collection));
    REQUIRE(id_collection.items.size() == 1u);
    CHECK(id_collection.items[0].material_phase == nullptr);
    CHECK((id_collection.items[0].flags & TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE) == 0u);

    const char* collected_uuid = item.payload.foliage_batch.foliage_uuid;
    layer->foliage_uuid = "changed";
    REQUIRE(item.payload.foliage_batch.foliage_uuid == collected_uuid);
    CHECK(std::strcmp(item.payload.foliage_batch.foliage_uuid, "foliage-render-item-test-asset") == 0);

    termin::TcFoliageData::clear_registry_for_tests();
    tc_mesh_shutdown();
    tc_material_shutdown();
}
