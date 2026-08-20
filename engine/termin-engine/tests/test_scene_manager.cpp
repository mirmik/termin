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

TEST_CASE("SceneManager atomically rekeys a registered scene") {
    termin::SceneManager manager;
    const termin::SceneKey untitled("untitled", termin::SceneRole::Authoring);
    const termin::SceneKey saved("Scenes/Main.scene", termin::SceneRole::Authoring);
    const termin::SceneKey occupied("Scenes/Occupied.scene", termin::SceneRole::Authoring);
    const tc_scene_handle scene = manager.create_scene(untitled);
    const tc_scene_handle other = manager.create_scene(occupied);
    REQUIRE(tc_scene_handle_valid(scene));
    REQUIRE(tc_scene_handle_valid(other));
    REQUIRE(manager.set_scene_path(untitled, "/project/Scenes/Main.scene"));

    REQUIRE(manager.rekey_scene(untitled, saved));
    CHECK_FALSE(manager.has_scene(untitled));
    CHECK(tc_scene_handle_eq(manager.get_scene(saved), scene));
    CHECK_EQ(manager.get_scene_path(saved), std::string("/project/Scenes/Main.scene"));
    REQUIRE(manager.key_of(scene).has_value());
    CHECK(manager.key_of(scene).value() == saved);

    CHECK_FALSE(manager.rekey_scene(saved, occupied));
    CHECK(tc_scene_handle_eq(manager.get_scene(saved), scene));
    CHECK(tc_scene_handle_eq(manager.get_scene(occupied), other));
    CHECK_FALSE(manager.rekey_scene(untitled, saved));
    CHECK_FALSE(manager.rekey_scene(
        saved,
        termin::SceneKey("Scenes/Main.scene", termin::SceneRole::Runtime)));
}

TEST_CASE("SceneManager elevation is explicit, validated and recursion-safe") {
    termin::SceneManager manager;
    const termin::SceneKey runtime("Scenes/Lazy.scene", termin::SceneRole::Runtime);
    int calls = 0;

    CHECK_FALSE(tc_scene_handle_valid(manager.elevate_scene(runtime)));
    manager.set_scene_elevator([&](const termin::SceneKey& key) {
        ++calls;
        CHECK(key == runtime);
        return tc_scene_handle_valid(manager.create_scene(key));
    });
    const tc_scene_handle scene = manager.elevate_scene(runtime);
    REQUIRE(tc_scene_handle_valid(scene));
    CHECK_EQ(calls, 1);
    CHECK(tc_scene_handle_eq(manager.elevate_scene(runtime), scene));
    CHECK_EQ(calls, 1);

    const termin::SceneKey recursive("Scenes/Recursive.scene", termin::SceneRole::Runtime);
    manager.set_scene_elevator([&](const termin::SceneKey& key) {
        CHECK_FALSE(tc_scene_handle_valid(manager.elevate_scene(key)));
        return true;
    });
    CHECK_FALSE(tc_scene_handle_valid(manager.elevate_scene(recursive)));
}
