#include "guard_main.h"

GUARD_TEST_MAIN();

#include <termin/scene/scene_manager.hpp>

TEST_CASE("SceneManager keys scene instances by identity and role") {
    termin::SceneManager manager;
    const termin::SceneKey authoring("Scenes/Main.scene", termin::SceneRole::Authoring);
    const termin::SceneKey runtime("Scenes/Main.scene", termin::SceneRole::Runtime);

    const tc_scene_handle authoring_scene = manager.create_scene(authoring);
    const tc_scene_handle runtime_scene = manager.create_scene(runtime);
    REQUIRE(tc_scene_handle_valid(authoring_scene));
    REQUIRE(tc_scene_handle_valid(runtime_scene));
    CHECK_FALSE(tc_scene_handle_eq(authoring_scene, runtime_scene));

    CHECK(manager.has_scene(authoring));
    CHECK(manager.has_scene(runtime));
    CHECK(tc_scene_handle_eq(manager.get_scene(authoring), authoring_scene));
    CHECK(tc_scene_handle_eq(manager.get_scene(runtime), runtime_scene));
    REQUIRE(manager.key_of(runtime_scene).has_value());
    CHECK_EQ(manager.key_of(runtime_scene)->identity, std::string("Scenes/Main.scene"));
    CHECK(manager.key_of(runtime_scene)->role == termin::SceneRole::Runtime);

    CHECK(manager.set_scene_path(authoring, "/source/Main.scene"));
    CHECK(manager.set_scene_path(runtime_scene, "/package/Main.scene"));
    CHECK_EQ(manager.get_scene_path(authoring_scene), std::string("/source/Main.scene"));
    CHECK_EQ(manager.get_scene_path(runtime), std::string("/package/Main.scene"));

    const auto entries = manager.scene_entries();
    CHECK_EQ(entries.size(), 2u);
    manager.close_scenes(termin::SceneRole::Runtime);
    CHECK(manager.has_scene(authoring));
    CHECK_FALSE(manager.has_scene(runtime));
}

TEST_CASE("SceneManager rejects duplicate keys and handles without replacing entries") {
    termin::SceneManager manager;
    const termin::SceneKey authoring("Scenes/Main.scene", termin::SceneRole::Authoring);
    const termin::SceneKey runtime("Scenes/Main.scene", termin::SceneRole::Runtime);
    const tc_scene_handle first = tc_scene_new();
    const tc_scene_handle second = tc_scene_new();
    REQUIRE(tc_scene_handle_valid(first));
    REQUIRE(tc_scene_handle_valid(second));

    REQUIRE(manager.register_scene(authoring, first));
    CHECK_FALSE(manager.register_scene(authoring, second));
    CHECK_FALSE(manager.register_scene(runtime, first));
    CHECK(tc_scene_handle_eq(manager.get_scene(authoring), first));
    CHECK_FALSE(manager.has_scene(runtime));
    CHECK_EQ(manager.scene_entries().size(), 1u);

    tc_scene_free(second);
    CHECK(manager.unregister_scene(authoring));
    CHECK_FALSE(manager.unregister_scene(authoring));
    tc_scene_free(first);
}
