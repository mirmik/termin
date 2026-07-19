#include "render/tc_display.h"
#include "render/tc_input_manager.h"
#include "render/tc_render_surface.h"
#include "render/tc_viewport.h"
#include "termin/input/window_input_bridge.hpp"
#include "termin/window/event.hpp"

#include <cassert>
#include <cstdio>

namespace {

struct FixedSurface {
    tc_render_surface surface;
    int width = 100;
    int height = 100;
};

struct CountingInput {
    tc_input_manager manager;
    int presses = 0;
    int releases = 0;
    uint32_t last_click_count = 0;
    double last_x = 0.0;
    double last_y = 0.0;
    uint32_t last_codepoint = 0;
};

void surface_get_size(tc_render_surface* self, int* width, int* height)
{
    auto* fixed = reinterpret_cast<FixedSurface*>(self);
    if (width) {
        *width = fixed->width;
    }
    if (height) {
        *height = fixed->height;
    }
}

void count_mouse_move(tc_input_manager* self, double x, double y)
{
    auto* input = reinterpret_cast<CountingInput*>(self->userdata);
    input->last_x = x;
    input->last_y = y;
}

void count_text(tc_input_manager* self, uint32_t codepoint)
{
    auto* input = reinterpret_cast<CountingInput*>(self->userdata);
    input->last_codepoint = codepoint;
}

void count_mouse_button(tc_input_manager* self, int, int action, int, uint32_t click_count)
{
    auto* input = reinterpret_cast<CountingInput*>(self->userdata);
    if (action == TC_INPUT_PRESS) {
        input->presses += 1;
    } else if (action == TC_INPUT_RELEASE) {
        input->releases += 1;
    }
    input->last_click_count = click_count;
}

const tc_render_surface_vtable fixed_surface_vtable = {
    .get_size = surface_get_size,
};

const tc_input_manager_vtable counting_input_vtable = {
    .on_mouse_button = count_mouse_button,
    .on_mouse_move = count_mouse_move,
    .on_char = count_text,
};

void init_counting_input(CountingInput* input)
{
    input->presses = 0;
    input->releases = 0;
    input->last_click_count = 0;
    input->last_x = 0.0;
    input->last_y = 0.0;
    input->last_codepoint = 0;
    tc_input_manager_init(&input->manager, &counting_input_vtable);
    input->manager.userdata = input;
}

} // namespace

int main()
{
    FixedSurface fixed_surface;
    tc_render_surface_init(&fixed_surface.surface, &fixed_surface_vtable);

    tc_display* display = tc_display_new("router-test-display", &fixed_surface.surface);
    assert(display != nullptr);

    tc_viewport_handle left = tc_viewport_new("left", TC_SCENE_HANDLE_INVALID);
    tc_viewport_handle right = tc_viewport_new("right", TC_SCENE_HANDLE_INVALID);
    assert(tc_viewport_handle_valid(left));
    assert(tc_viewport_handle_valid(right));

    tc_viewport_set_rect(left, 0.0f, 0.0f, 0.5f, 1.0f);
    tc_viewport_set_rect(right, 0.5f, 0.0f, 0.5f, 1.0f);
    tc_display_add_viewport(display, left);
    tc_display_add_viewport(display, right);

    CountingInput left_input;
    CountingInput right_input;
    init_counting_input(&left_input);
    init_counting_input(&right_input);
    tc_viewport_set_input_manager(left, &left_input.manager);
    tc_viewport_set_input_manager(right, &right_input.manager);
    assert(tc_viewport_get_input_manager(left) == &left_input.manager);
    assert(tc_viewport_get_input_manager(right) == &right_input.manager);

    tc_input_manager* input = tc_display_get_input_manager(display);
    assert(input != nullptr);
    assert(input->vtable != nullptr);
    assert(input->vtable->on_mouse_move != nullptr);
    assert(input->vtable->on_mouse_button != nullptr);
    assert(tc_viewport_handle_valid(tc_display_viewport_at_screen(display, 25.0f, 50.0f)));

    tc_display_dispatch_pointer_move(display, 25.0, 50.0);
    tc_display_dispatch_pointer_button(
        display, 25.0, 50.0, TC_MOUSE_BUTTON_LEFT, TC_INPUT_PRESS, 0, 2);

    FixedSurface replacement_surface;
    tc_render_surface_init(&replacement_surface.surface, &fixed_surface_vtable);
    tc_display_set_surface(display, &replacement_surface.surface);
    if (tc_display_get_input_manager(display) != input) {
        std::fprintf(stderr, "surface replacement changed the display input endpoint\n");
        return 1;
    }

    tc_display_dispatch_pointer_move(display, 75.0, 50.0);
    tc_display_dispatch_pointer_button(
        display, 75.0, 50.0, TC_MOUSE_BUTTON_LEFT, TC_INPUT_RELEASE, 0, 2);

    if (left_input.presses != 1 || left_input.releases != 1 ||
        right_input.presses != 0 || right_input.releases != 0 ||
        left_input.last_click_count != 2) {
        std::fprintf(stderr,
                     "unexpected routing: left press=%d release=%d, right press=%d release=%d\n",
                     left_input.presses,
                     left_input.releases,
                     right_input.presses,
                     right_input.releases);
        return 1;
    }

    termin::WindowEvent pointer_event;
    pointer_event.type = termin::WindowEventType::PointerMoved;
    pointer_event.pointer.logical_position = {12.5f, 25.0f};
    pointer_event.pointer.framebuffer_position = {75.0f, 50.0f};
    termin::dispatch_window_input_event(display, pointer_event);
    if (right_input.last_x != 75.0 || right_input.last_y != 50.0) {
        std::fprintf(stderr, "window bridge used logical instead of framebuffer coordinates\n");
        return 1;
    }

    termin::WindowEvent text_event;
    text_event.type = termin::WindowEventType::TextInput;
    text_event.text.utf8[0] = static_cast<char>(0xd0);
    text_event.text.utf8[1] = static_cast<char>(0x96);
    termin::dispatch_window_input_event(display, text_event);
    if (left_input.last_codepoint != 0x416) {
        std::fprintf(stderr, "window bridge did not decode UTF-8 text input\n");
        return 1;
    }

    tc_display_free(display);
    return 0;
}
