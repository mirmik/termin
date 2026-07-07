#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cstring>
#include <vector>

#include <termin/foliage/foliage_data_registry.hpp>
#include <termin/foliage/foliage_layer_component.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

extern "C" {
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
}

namespace {

termin::TcMesh make_test_mesh()
{
    const float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
    };
    const uint32_t indices[] = {0, 1, 2};
    return termin::TcMesh::from_interleaved(
        vertices,
        3,
        indices,
        3,
        tc_vertex_layout_pos(),
        "foliage-render-item-test-mesh",
        "foliage-render-item-test-mesh");
}

} // namespace

TEST_CASE("FoliageLayerComponent emits foliage batch render items with owned asset id")
{
    tc_material_init();
    tc_mesh_init();
    termin::TcFoliageData::clear_registry_for_tests();

    termin::TcFoliageData foliage = termin::TcFoliageData::declare(
        "foliage-render-item-test-asset",
        "foliage-render-item-test-asset");
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

    tc_material_handle material_handle = tc_material_create(
        "foliage-render-item-test-material",
        "foliage-render-item-test-material");
    REQUIRE(tc_material_is_valid(material_handle));
    tc_material* material = tc_material_get(material_handle);
    REQUIRE(material != nullptr);
    tc_material_phase* phase = tc_material_add_phase(
        material,
        tc_shader_handle_invalid(),
        "opaque",
        3);
    REQUIRE(phase != nullptr);

    termin::TcSceneRef scene = termin::TcSceneRef::create("foliage-render-item-test-scene");
    termin::Entity entity = scene.create_entity("foliage");
    auto* layer = new termin::FoliageLayerComponent();
    layer->foliage_uuid = foliage.uuid();
    layer->prototype_mesh = mesh;
    layer->material = termin::TcMaterial(material_handle);
    entity.add_component(layer);

    tc_render_item_collect_context collect_context{};
    collect_context.phase_mark = "opaque";
    collect_context.debug_pass_name = "ColorPass";

    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(
        layer->tc_component_ptr(),
        collect_context,
        collection));

    REQUIRE(collection.items.size() == 1u);
    const tc_render_item& item = collection.items[0];
    CHECK(item.kind == TC_RENDER_ITEM_KIND_FOLIAGE_BATCH);
    CHECK(item.component == layer->tc_component_ptr());
    CHECK(item.geometry_id == 0);
    CHECK(item.material_phase == phase);
    CHECK((item.flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) != 0u);
    CHECK((item.flags & TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE) != 0u);
    CHECK(item.payload.foliage_batch.prototype_mesh == mesh.get());
    CHECK(!tc_mesh_handle_is_invalid(item.payload.foliage_batch.prototype_mesh_handle));
    REQUIRE(item.payload.foliage_batch.foliage_uuid != nullptr);
    CHECK(std::strcmp(
        item.payload.foliage_batch.foliage_uuid,
        "foliage-render-item-test-asset") == 0);

    const char* collected_uuid = item.payload.foliage_batch.foliage_uuid;
    layer->foliage_uuid = "changed";
    REQUIRE(item.payload.foliage_batch.foliage_uuid == collected_uuid);
    CHECK(std::strcmp(
        item.payload.foliage_batch.foliage_uuid,
        "foliage-render-item-test-asset") == 0);

    termin::TcFoliageData::clear_registry_for_tests();
    tc_mesh_shutdown();
    tc_material_shutdown();
}
