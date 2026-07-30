#include "render/tc_display.h"
#include "render/tc_input_manager.h"
#include "render/tc_render_surface.h"
#include "render/tc_viewport.h"
#include "tc_input_event.h"
#ifdef TERMIN_DISPLAY_HAS_SDL
#include "termin/input/window_input_bridge.hpp"
#include "termin/window/event.hpp"
#endif

#include <cassert>
#include <cstdio>
#include <string>

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
    std::string last_text;
    int focus_lost = 0;
    int last_key = -1;
    int last_scancode = -1;
    int last_key_action = -1;
    int pointer_events = 0;
    uint64_t last_pointer_id = 0;
    int last_pointer_phase = -1;
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

uint32_t surface_get_color_texture_id(tc_render_surface*) { return 1; }
uintptr_t surface_get_graphics_domain_key(tc_render_surface*) { return 1; }
void surface_destroy(tc_render_surface*) {}
bool surface_resize(tc_render_surface* surface, int width, int height) {
    auto* fixed = static_cast<FixedSurface*>(surface->body);
    fixed->width = width;
    fixed->height = height;
    tc_render_surface_notify_resize(surface, width, height);
    return true;
}
void surface_delete(tc_render_surface* surface) {
    delete static_cast<FixedSurface*>(surface->body);
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

void count_text_utf8(tc_input_manager* self, const char* text_utf8)
{
    auto* input = reinterpret_cast<CountingInput*>(self->userdata);
    input->last_text = text_utf8 ? text_utf8 : "";
}

void count_focus_lost(tc_input_manager* self)
{
    auto* input = reinterpret_cast<CountingInput*>(self->userdata);
    input->focus_lost += 1;
}

void count_key(tc_input_manager* self, int key, int scancode, int action, int)
{
    auto* input = reinterpret_cast<CountingInput*>(self->userdata);
    input->last_key = key;
    input->last_scancode = scancode;
    input->last_key_action = action;
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

void count_pointer(tc_input_manager* self, uint64_t pointer_id, int, int phase,
                   double x, double y, float)
{
    auto* input = reinterpret_cast<CountingInput*>(self->userdata);
    input->pointer_events += 1;
    input->last_pointer_id = pointer_id;
    input->last_pointer_phase = phase;
    input->last_x = x;
    input->last_y = y;
}

const tc_render_surface_vtable fixed_surface_vtable = {
    .get_size = surface_get_size,
    .resize = surface_resize,
    .get_color_texture_id = surface_get_color_texture_id,
    .get_graphics_domain_key = surface_get_graphics_domain_key,
    .destroy = surface_destroy,
};

const tc_input_manager_vtable counting_input_vtable = {
    .on_pointer = count_pointer,
    .on_mouse_button = count_mouse_button,
    .on_mouse_move = count_mouse_move,
    .on_key = count_key,
    .on_char = count_text,
    .on_text = count_text_utf8,
    .on_focus_lost = count_focus_lost,
};

void init_counting_input(CountingInput* input)
{
    input->presses = 0;
    input->releases = 0;
    input->last_click_count = 0;
    input->last_x = 0.0;
    input->last_y = 0.0;
    input->last_codepoint = 0;
    input->last_text.clear();
    input->focus_lost = 0;
    input->last_key = -1;
    input->last_scancode = -1;
    input->last_key_action = -1;
    input->pointer_events = 0;
    input->last_pointer_id = 0;
    input->last_pointer_phase = -1;
    tc_input_manager_init(&input->manager, &counting_input_vtable);
    input->manager.userdata = input;
}

} // namespace

int main()
{
    tc_display_pool_init();
    auto* fixed_surface = new FixedSurface;
    tc_render_surface_init(
        &fixed_surface->surface, &fixed_surface_vtable, surface_delete);
    fixed_surface->surface.body = fixed_surface;

    tc_display_handle display = tc_display_new("router-test-display", &fixed_surface->surface);
    assert(tc_display_handle_valid(display));

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

    auto* replacement_surface = new FixedSurface;
    tc_render_surface_init(
        &replacement_surface->surface, &fixed_surface_vtable, surface_delete);
    replacement_surface->surface.body = replacement_surface;
    assert(tc_display_set_surface(display, &replacement_surface->surface));
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

    // A touch remains captured by the viewport where it started even after
    // crossing into another viewport.
    assert(tc_display_dispatch_pointer(
        display, 42, TC_POINTER_DEVICE_TOUCH, TC_POINTER_DOWN,
        25.0, 50.0, 1.0f));
    assert(tc_display_dispatch_pointer(
        display, 42, TC_POINTER_DEVICE_TOUCH, TC_POINTER_MOVE,
        75.0, 50.0, 1.0f));
    assert(tc_display_dispatch_pointer(
        display, 42, TC_POINTER_DEVICE_TOUCH, TC_POINTER_UP,
        75.0, 50.0, 0.0f));
    assert(left_input.pointer_events == 3);
    assert(right_input.pointer_events == 0);
    assert(left_input.last_pointer_id == 42);
    assert(left_input.last_pointer_phase == TC_POINTER_UP);

    // Capture is released after UP, so reusing the platform pointer id starts
    // a new contact in the viewport under the new DOWN position.
    assert(tc_display_dispatch_pointer(
        display, 42, TC_POINTER_DEVICE_TOUCH, TC_POINTER_DOWN,
        75.0, 50.0, 1.0f));
    assert(right_input.pointer_events == 1);
    assert(tc_display_dispatch_pointer(
        display, 42, TC_POINTER_DEVICE_TOUCH, TC_POINTER_CANCEL,
        75.0, 50.0, 0.0f));
    assert(right_input.pointer_events == 2);

#ifdef TERMIN_DISPLAY_HAS_SDL
    termin::WindowEvent pointer_event;
    pointer_event.type = termin::WindowEventType::PointerMoved;
    pointer_event.pointer.logical_position = {12.5f, 25.0f};
    pointer_event.pointer.framebuffer_position = {75.0f, 50.0f};
    termin::dispatch_window_input_event(display, pointer_event);
    if (right_input.last_x != 25.0 || right_input.last_y != 50.0) {
        std::fprintf(
            stderr,
            "window bridge did not route framebuffer coordinates in viewport-local space\n");
        return 1;
    }

    termin::WindowEvent key_event;
    key_event.type = termin::WindowEventType::KeyPressed;
    key_event.key.key = termin::WindowKey::W;
    key_event.key.native_key = 'w';
    key_event.key.native_scancode = 26;
    termin::dispatch_window_input_event(display, key_event);
    if (left_input.last_key != TC_KEY_W ||
        left_input.last_scancode != 26 ||
        left_input.last_key_action != TC_INPUT_PRESS) {
        std::fprintf(
            stderr,
            "window bridge did not translate portable key code: "
            "key=%d scancode=%d action=%d\n",
            left_input.last_key,
            left_input.last_scancode,
            left_input.last_key_action);
        return 1;
    }

    termin::WindowEvent text_event;
    text_event.type = termin::WindowEventType::TextInput;
    text_event.text.utf8[0] = static_cast<char>(0xd0);
    text_event.text.utf8[1] = static_cast<char>(0x96);
    termin::dispatch_window_input_event(display, text_event);
    if (left_input.last_text != "\xd0\x96") {
        std::fprintf(stderr, "window bridge did not preserve committed UTF-8 text\n");
        return 1;
    }

    termin::WindowEvent focus_event;
    focus_event.type = termin::WindowEventType::FocusLost;
    termin::dispatch_window_input_event(display, focus_event);
    if (left_input.focus_lost != 1 || right_input.focus_lost != 1) {
        std::fprintf(stderr, "window focus loss was not broadcast to viewport inputs\n");
        return 1;
    }
#endif

    tc_display_free(display);
    tc_display_pool_shutdown();
    return 0;
}
