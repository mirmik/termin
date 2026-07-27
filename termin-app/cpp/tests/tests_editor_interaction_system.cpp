#include "guard_main.h"

#include "termin/editor/editor_interaction_system.hpp"

TEST_CASE("EditorInteractionSystem ignores release without scene press")
{
    termin::EditorInteractionSystem interaction;
    int click_callbacks = 0;
    interaction.on_entity_click = [&](auto&&...) -> bool {
        click_callbacks += 1;
        return false;
    };

    interaction.on_mouse_button(
        0,
        TC_INPUT_RELEASE,
        0,
        1,
        12.0f,
        34.0f,
        TC_VIEWPORT_HANDLE_INVALID,
        TC_DISPLAY_HANDLE_INVALID);
    interaction.after_render();

    CHECK_EQ(click_callbacks, 0);
}

TEST_CASE("EditorInteractionSystem coalesces stale picking render requests")
{
    termin::EditorInteractionSystem interaction;
    int scene_requests = 0;
    interaction.on_request_scene_render = [&]() {
        scene_requests += 1;
    };

    interaction.on_mouse_move(
        12.0f,
        34.0f,
        0.0f,
        0.0f,
        TC_VIEWPORT_HANDLE_INVALID,
        TC_DISPLAY_HANDLE_INVALID);
    interaction.on_mouse_move(
        13.0f,
        35.0f,
        1.0f,
        1.0f,
        TC_VIEWPORT_HANDLE_INVALID,
        TC_DISPLAY_HANDLE_INVALID);

    CHECK_EQ(scene_requests, 1);
    CHECK_EQ(interaction.picking_scene_request_count(), 1);
    CHECK_FALSE(interaction.id_buffer_fresh());

    interaction.after_render();
    CHECK(interaction.id_buffer_fresh());
    CHECK_EQ(interaction.id_buffer_version(), 1);

    interaction.on_mouse_move(
        14.0f,
        36.0f,
        1.0f,
        1.0f,
        TC_VIEWPORT_HANDLE_INVALID,
        TC_DISPLAY_HANDLE_INVALID);
    interaction.poll_picking();

    CHECK_EQ(scene_requests, 1);
    CHECK(interaction.picking_poll_count() >= 2);
}
