#include "guard_main.h"
#include "sprite_test_types.hpp"

GUARD_TEST_MAIN();

#include <cmath>

#include <termin/render/render_item_submission.hpp>
#include <termin/render/sprite_asset.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx/tgfx_texture_handle.hpp>

extern "C" {
#include <tgfx/resources/tc_texture_registry.h>
}

TEST_CASE("SpriteRenderer2D emits canonical XZ world quad and typed asset ref") {
    tc_texture_init();
    termin::TcSpriteAsset::clear_registry_for_tests();
    register_sprite_test_types();

    const uint8_t pixels[4 * 8 * 4] = {};
    termin::TcTexture texture = termin::TcTexture::from_data(termin::TcTextureCreateInfo{
        {pixels, sizeof(pixels), 8, 4, 4},
        {},
        "atlas",
        "",
        "sprite-renderer-test-texture",
    });
    REQUIRE(texture.is_valid());

    termin::TcSpriteAsset sprite = termin::TcSpriteAsset::declare("sprite-renderer-test-sprite", "hero");
    REQUIRE(sprite.update(texture.uuid(), {2, 1, 4, 2}, 8, 4, 0.25f, 0.5f, 2.0f, termin::SpriteSampling::Nearest));
    const uint32_t loaded_version = sprite.version();
    sprite.unload();
    CHECK_FALSE(sprite.is_loaded());
    CHECK_EQ(sprite.version(), loaded_version + 1);
    REQUIRE(sprite.update(texture.uuid(), {2, 1, 4, 2}, 8, 4, 0.25f, 0.5f, 2.0f, termin::SpriteSampling::Nearest));
    CHECK(sprite.is_loaded());

    termin::TcSceneRef scene = termin::TcSceneRef::create("sprite-renderer-test-scene");
    termin::Entity entity = scene.create_entity("hero");
    auto* renderer = new termin::SpriteRenderer2D();
    renderer->set_sprite_uuid(sprite.uuid());
    renderer->set_sorting_layer(3);
    renderer->set_order_in_layer(-2);
    entity.add_component(renderer);

    tc_render_item_collect_context context{};
    context.phase = TC_PHASE_NONE;
    size_t material_count = 0;
    tc_material_sink material_sink{};
    material_sink.emit = [](tc_material_handle, void* user_data) {
        ++*static_cast<size_t*>(user_data);
        return true;
    };
    material_sink.user_data = &material_count;
    REQUIRE(renderer->collect_materials(context, material_sink));
    CHECK_EQ(material_count, 0u);
    termin::RenderItemCollection collection;
    REQUIRE(termin::collect_drawable_render_items(renderer->tc_component_ptr(), context, collection));
    REQUIRE_EQ(collection.items.size(), 1u);
    const tc_render_item& item = collection.items.front();
    CHECK_EQ(item.kind, static_cast<uint32_t>(TC_RENDER_ITEM_KIND_WORLD_QUAD));
    CHECK(tc_material_handle_is_invalid(item.material));
    CHECK_EQ(item.material_phase_index, SIZE_MAX);
    CHECK_EQ(item.payload.world_quad.sorting_layer, 3);
    CHECK_EQ(item.payload.world_quad.order_in_layer, -2);
    CHECK_EQ(item.payload.world_quad.sampling, static_cast<uint32_t>(TC_WORLD_QUAD_SAMPLING_NEAREST));
    CHECK(std::abs(item.payload.world_quad.min_x - -0.5f) < 1.0e-6f);
    CHECK(std::abs(item.payload.world_quad.max_x - 1.5f) < 1.0e-6f);
    CHECK(std::abs(item.payload.world_quad.min_z - -0.5f) < 1.0e-6f);
    CHECK(std::abs(item.payload.world_quad.max_z - 0.5f) < 1.0e-6f);

    tc_value data = renderer->serialize_data();
    tc_value* serialized_sprite = tc_value_dict_get(&data, "sprite");
    REQUIRE(serialized_sprite != nullptr);
    REQUIRE(serialized_sprite->type == TC_VALUE_DICT);
    tc_value* kind = tc_value_dict_get(serialized_sprite, "kind");
    tc_value* uuid = tc_value_dict_get(serialized_sprite, "uuid");
    REQUIRE(kind && kind->type == TC_VALUE_STRING);
    REQUIRE(uuid && uuid->type == TC_VALUE_STRING);
    CHECK_EQ(std::string(kind->data.s), "sprite_asset");
    CHECK_EQ(std::string(uuid->data.s), "sprite-renderer-test-sprite");
    tc_value_free(&data);

    double ray_parameter = 0.0;
    termin::Ray3 ray;
    ray.origin = {0.0, -2.0, 0.0};
    ray.direction = {0.0, 2.0, 0.0};
    CHECK(renderer->ray_intersects(ray, &ray_parameter));
    CHECK(std::abs(ray_parameter - 1.0) < 1.0e-6);

    scene.destroy();
    texture = {};
    tc_texture_shutdown();
}

TEST_CASE("Sprite UUID fields round-trip through the inspector and typed scene data") {
    register_sprite_test_types();

    const auto check_field = [](auto& component, auto& restored, const char* field) {
        tc_value input = tc_value_string("inspector-asset-ref");
        REQUIRE(tc_inspect_set_checked(&component, component.type_name(), field, input, nullptr));
        tc_value_free(&input);
        tc_value saved = component.serialize_data();
        const auto* reference = tc_value_dict_get(&saved, field);
        REQUIRE(reference && reference->type == TC_VALUE_DICT);
        restored.deserialize_data(&saved);
        tc_value_free(&saved);
        tc_value actual = tc_inspect_get(&restored, restored.type_name(), field);
        REQUIRE(actual.type == TC_VALUE_STRING);
        CHECK_EQ(std::string(actual.data.s), "inspector-asset-ref");
        tc_value_free(&actual);
    };
    termin::SpriteRenderer2D renderer, restored_renderer;
    check_field(renderer, restored_renderer, "sprite");
    CHECK_EQ(restored_renderer.sprite_uuid, "inspector-asset-ref");
    tc_value channels = tc_value_list_new();
    for (double channel : {0.125, 0.25, 0.5, 0.75}) tc_value_list_push(&channels, tc_value_double(channel));
    REQUIRE(tc_inspect_set_checked(&renderer, renderer.type_name(), "tint", channels, nullptr));
    tc_value_free(&channels);
    tc_value saved = renderer.serialize_data();
    restored_renderer.deserialize_data(&saved);
    tc_value_free(&saved);
    CHECK_EQ(restored_renderer.tint.x, 0.125);
    CHECK_EQ(restored_renderer.tint.y, 0.25);
    CHECK_EQ(restored_renderer.tint.z, 0.5);
    CHECK_EQ(restored_renderer.tint.w, 0.75);

    termin::SpriteAnimator2D animator, restored_animator;
    check_field(animator, restored_animator, "clip");
    CHECK_EQ(restored_animator.clip_uuid(), "inspector-asset-ref");
}
