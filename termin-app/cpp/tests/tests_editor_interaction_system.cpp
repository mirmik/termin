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
        12.0f,
        34.0f,
        TC_VIEWPORT_HANDLE_INVALID,
        nullptr);
    interaction.after_render();

    CHECK_EQ(click_callbacks, 0);
}
