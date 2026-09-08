#include "guard_main.h"

#include "termin/editor/editor_interaction_system.hpp"
#include "termin/editor/editor_viewport_input_manager.hpp"

#include <core/tc_component.h>
#include <core/tc_input_capability.h>
#include <core/tc_input_component.h>
#include <render/tc_display.h>
#include <render/tc_viewport.h>

#include <string>
#include <utility>
#include <vector>

namespace {

    struct InputProbe {
        tc_component component{};
        bool accept_down = false;
        std::vector<std::pair<std::string, int>> events;
        int focus_lost = 0;
    };

    InputProbe* probe(tc_component* component) {
        return reinterpret_cast<InputProbe*>(component);
    }

    void on_mouse_button(tc_component* component, tc_mouse_button_event* event) {
        auto* state = probe(component);
        state->events.emplace_back(event->action == TC_INPUT_PRESS ? "down" : "up", event->button);
        if (event->action == TC_INPUT_PRESS && state->accept_down)
            event->handled = true;
    }

    void on_mouse_move(tc_component* component, tc_mouse_move_event*) {
        probe(component)->events.emplace_back("move", -1);
    }

    void on_focus_lost(tc_component* component, tc_input_focus_event*) {
        ++probe(component)->focus_lost;
    }

    const tc_input_vtable input_vtable = {
        .on_mouse_button = on_mouse_button,
        .on_mouse_move = on_mouse_move,
        .on_focus_lost = on_focus_lost,
    };

    void init_probe(InputProbe& state, tc_entity_handle entity) {
        tc_component_init(&state.component, nullptr);
        REQUIRE(tc_input_capability_attach(&state.component, &input_vtable));
        REQUIRE(tc_component_set_input_source_mask(&state.component, TC_INPUT_SOURCE_EDITOR));
        tc_entity_add_component(entity, &state.component);
    }

    void clear_probe(InputProbe& state, tc_entity_handle entity) {
        tc_entity_remove_component(entity, &state.component);
        tc_component_clear_capabilities(&state.component);
    }

} // namespace

TEST_CASE("Editor viewport retains one native pointer owner and initiating button") {
    const tc_scene_handle scene = tc_scene_new_named("editor-pointer-owner-scene");
    const tc_scene_handle internal_scene = tc_scene_new_named("editor-pointer-owner-internal-scene");
    REQUIRE(tc_scene_alive(scene));
    REQUIRE(tc_scene_alive(internal_scene));
    const tc_entity_pool_handle scene_pool = tc_entity_pool_registry_find(tc_scene_entity_pool(scene));
    const tc_entity_pool_handle internal_pool = tc_entity_pool_registry_find(tc_scene_entity_pool(internal_scene));
    REQUIRE(tc_entity_pool_handle_valid(scene_pool));
    REQUIRE(tc_entity_pool_handle_valid(internal_pool));
    const tc_entity_handle scene_entity = tc_entity_create(scene_pool, "scene-owner");
    const tc_entity_handle internal_entity = tc_entity_create(internal_pool, "internal-owner");
    REQUIRE(tc_entity_handle_valid(scene_entity));
    REQUIRE(tc_entity_handle_valid(internal_entity));

    InputProbe internal;
    InputProbe external;
    init_probe(internal, internal_entity);
    init_probe(external, scene_entity);
    internal.accept_down = true;
    external.accept_down = true;

    const tc_viewport_handle viewport = tc_viewport_new("editor-pointer-owner-viewport", scene);
    const tc_display_handle display = tc_display_new("editor-pointer-owner-display", nullptr);
    REQUIRE(tc_viewport_handle_valid(viewport));
    REQUIRE(tc_display_handle_valid(display));
    tc_viewport_set_internal_entities(viewport, internal_entity);
    termin::EditorViewportInputManager manager(viewport, display);

    manager.on_mouse_move(10.0, 20.0);
    internal.events.clear();
    external.events.clear();
    manager.on_mouse_button(0, TC_INPUT_PRESS, 0, 1);
    external.accept_down = true;
    manager.on_mouse_move(14.0, 25.0);
    manager.on_mouse_button(1, TC_INPUT_RELEASE, 0, 1);
    manager.on_mouse_button(0, TC_INPUT_RELEASE, 0, 1);

    REQUIRE_EQ(internal.events.size(), 3);
    CHECK(internal.events[0] == std::make_pair(std::string("down"), 0));
    CHECK(internal.events[1] == std::make_pair(std::string("move"), -1));
    CHECK(internal.events[2] == std::make_pair(std::string("up"), 0));
    CHECK(external.events.empty());

    internal.accept_down = false;
    manager.on_mouse_button(0, TC_INPUT_PRESS, 0, 1);
    manager.on_mouse_move(15.0, 26.0);
    manager.on_focus_lost();
    const std::vector<std::pair<std::string, int>> expected_external_events{{"down", 0}, {"move", -1}};
    CHECK(external.events == expected_external_events);
    CHECK_EQ(internal.focus_lost, 1);
    CHECK_EQ(external.focus_lost, 1);
    manager.on_mouse_button(1, TC_INPUT_RELEASE, 0, 1);
    manager.on_mouse_button(0, TC_INPUT_RELEASE, 0, 1);
    CHECK_EQ(external.events.size(), 2);

    manager.detach();
    clear_probe(internal, internal_entity);
    clear_probe(external, scene_entity);
    tc_viewport_free(viewport);
    tc_display_free(display);
    tc_entity_free(internal_entity);
    tc_entity_free(scene_entity);
    tc_scene_free(internal_scene);
    tc_scene_free(scene);
}

TEST_CASE("Editor viewport dead detach cancels the global Python pointer owner") {
    const tc_scene_handle scene = tc_scene_new_named("editor-dead-viewport-pointer-owner-scene");
    REQUIRE(tc_scene_alive(scene));
    const tc_viewport_handle viewport = tc_viewport_new("editor-dead-viewport-pointer-owner", scene);
    const tc_display_handle display = tc_display_new("editor-dead-viewport-pointer-owner", nullptr);
    REQUIRE(tc_viewport_handle_valid(viewport));
    REQUIRE(tc_display_handle_valid(display));

    termin::EditorInteractionSystem interaction;
    std::vector<std::string> phases;
    interaction.on_viewport_pointer_event = [&](const termin::ViewportPointerEvent& event) {
        phases.push_back(event.phase);
        return event.phase == "down";
    };
    termin::EditorViewportInputManager manager(viewport, display);
    manager.on_mouse_move(20.0, 30.0);
    phases.clear();
    manager.on_mouse_button(0, TC_INPUT_PRESS, 0, 1);
    REQUIRE(phases == std::vector<std::string>{"down"});

    tc_viewport_free(viewport);
    manager.detach();
    CHECK(phases == std::vector<std::string>({"down", "cancel"}));
    manager.detach();
    CHECK_EQ(phases.size(), 2);

    tc_display_free(display);
    tc_scene_free(scene);
}
