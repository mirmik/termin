#include "guard_main.h"
#include "sprite_test_types.hpp"

GUARD_TEST_MAIN();

#include <algorithm>
#include <string>
#include <vector>

#include <tcbase/tc_log.h>
#include <termin/tc_scene.hpp>

namespace {
    struct Fixture {
        termin::TcSceneRef scene;
        termin::Entity entity;
        termin::SpriteRenderer2D* renderer;
        termin::SpriteAnimator2D* animator;
        termin::TcSpriteAnimationClip clip;

        Fixture() {
            register_sprite_test_types();
            for (const char* name : {"red", "green", "blue"}) {
                auto sprite = termin::TcSpriteAsset::declare(name, name);
                REQUIRE(sprite.update("atlas", {0, 0, 1, 1}, 1, 1, 0.5, 0.5, 1.0, termin::SpriteSampling::Nearest));
            }
            clip = termin::TcSpriteAnimationClip::declare("walk", "Walk");
            REQUIRE(clip.update({{"red", 0.25, "heel"}, {"green", 0.5, ""}, {"blue", 0.25, "toe"}}));
            scene = termin::TcSceneRef::create("flipbook");
            entity = scene.create_entity("actor");
            renderer = new termin::SpriteRenderer2D;
            renderer->set_sprite_uuid("rest");
            entity.add_component(renderer);
            animator = new termin::SpriteAnimator2D;
            animator->set_clip_uuid("walk");
            entity.add_component(animator);
        }
        ~Fixture() {
            scene.destroy();
        }
    };
} // namespace

TEST_CASE("Sprite animator sends each crossed marker and preserves authoring during editor preview") {
    Fixture f;
    std::vector<std::string> events;
    f.animator->set_frame_event_callback([&](const std::string& name, size_t frame) {
        events.push_back(name);
        CHECK_EQ(frame, f.animator->current_frame());
    });
    f.scene.editor_update(0);
    REQUIRE_EQ(f.renderer->effective_sprite_uuid(), "red");
    f.scene.editor_update(0.25);
    REQUIRE_EQ(f.renderer->effective_sprite_uuid(), "green");
    f.scene.editor_update(2.5);
    REQUIRE_EQ(f.animator->current_frame(), 2u);
    REQUIRE_EQ(f.animator->current_time(), 0.75);
    CHECK((events == std::vector<std::string>{"heel", "toe", "heel", "toe", "heel", "toe"}));
    tc_value data = f.renderer->serialize_data();
    auto* ref = tc_value_dict_get(&data, "sprite");
    REQUIRE(ref && ref->type == TC_VALUE_DICT);
    CHECK_EQ(std::string(tc_value_dict_get(ref, "uuid")->data.s), "rest");
    tc_value_free(&data);
    data = f.animator->serialize_data();
    ref = tc_value_dict_get(&data, "clip");
    REQUIRE(ref && ref->type == TC_VALUE_DICT);
    CHECK_EQ(std::string(tc_value_dict_get(ref, "uuid")->data.s), "walk");
    CHECK_EQ(std::string(tc_value_dict_get(ref, "kind")->data.s), "sprite_animation_clip");
    tc_value_free(&data);
}

TEST_CASE("Sprite playback controls hold or rewind without duplicate markers") {
    Fixture f;
    f.animator->autoplay = false;
    f.animator->loop = false;
    f.animator->set_speed(2);
    std::vector<std::string> events;
    f.animator->set_frame_event_callback([&](const std::string& name, size_t) { events.push_back(name); });
    f.scene.update(0.25);
    REQUIRE(!f.animator->playing());
    REQUIRE_EQ(f.animator->current_time(), 0.0);
    CHECK(events.empty());
    f.animator->play();
    f.scene.update(0.125);
    REQUIRE_EQ(f.animator->current_frame(), 1u);
    f.animator->pause();
    f.scene.update(1.0);
    CHECK_EQ(f.animator->current_time(), 0.25);
    f.animator->play();
    f.scene.update(1.0);
    CHECK(!f.animator->playing());
    CHECK_EQ(f.animator->current_time(), 1.0);
    CHECK_EQ(f.renderer->effective_sprite_uuid(), "blue");
    f.animator->stop();
    CHECK_EQ(f.renderer->effective_sprite_uuid(), "red");
    CHECK((events == std::vector<std::string>{"heel", "toe"}));
    f.animator->play();
    CHECK_EQ(events.size(), 3u);
    f.animator->set_speed(0);
    f.scene.update(0.5);
    CHECK_EQ(f.animator->current_time(), 0.0);
    f.entity.remove_component(f.animator);
    CHECK_EQ(f.renderer->effective_sprite_uuid(), "rest");
}

TEST_CASE("Reload restarts a playing clip with its replacement frames and missing frames are diagnosed") {
    Fixture f;
    f.scene.update(0.75);
    REQUIRE_EQ(f.renderer->effective_sprite_uuid(), "blue");
    f.clip.unload();
    f.scene.update(0.0);
    CHECK_EQ(f.renderer->effective_sprite_uuid(), "rest");
    REQUIRE(f.clip.update({{"green", 0.5, ""}, {"absent-sprite", 0.5, ""}}));
    f.scene.update(0);
    REQUIRE_EQ(f.renderer->effective_sprite_uuid(), "green");
    REQUIRE_EQ(f.animator->current_frame(), 0u);
    REQUIRE(tc_log_capture_start(16));
    f.scene.update(0.5);
    tc_log_record records[16];
    const auto count = tc_log_capture_drain(records, 16, nullptr);
    tc_log_capture_stop();
    CHECK(std::any_of(records, records + count, [](const auto& r) {
        return r.level == TC_LOG_ERROR && std::string(r.message).find("absent-sprite") != std::string::npos;
    }));
    CHECK_EQ(f.renderer->effective_sprite_uuid(), "absent-sprite");
}

TEST_CASE("A marker callback may pause on its exact boundary or replace a renderer") {
    Fixture f;
    f.scene.update(0);
    f.animator->set_frame_event_callback([&](const std::string& name, size_t) {
        if (name == "toe")
            f.animator->pause();
    });
    f.scene.update(2);
    REQUIRE(!f.animator->playing());
    REQUIRE_EQ(f.animator->current_time(), 0.75);
    REQUIRE_EQ(f.renderer->effective_sprite_uuid(), "blue");

    f.animator->play();
    f.animator->set_frame_event_callback([&](const std::string&, size_t) { f.entity.remove_component(f.renderer); });
    f.scene.update(1);
    CHECK_EQ(f.animator->current_time(), 0.0);
    CHECK(!f.entity.get_component<termin::SpriteRenderer2D>());
    f.renderer = new termin::SpriteRenderer2D;
    f.entity.add_component(f.renderer);
    f.scene.update(0.125);
    CHECK_EQ(f.renderer->effective_sprite_uuid(), "red");
}

TEST_CASE("Marker-free playback skips whole loops at high speed even when subscribed") {
    Fixture f;
    REQUIRE(f.clip.update({{"green", 0.25, ""}, {"blue", 0.75, ""}}));
    f.animator->set_frame_event_callback([](const std::string&, size_t) { CHECK(false); });
    f.animator->set_speed(1000000000.25);
    f.scene.update(1);
    CHECK_EQ(f.animator->current_time(), 0.25);
    CHECK_EQ(f.renderer->effective_sprite_uuid(), "blue");
}
