#include "core/tc_component.h"
#include "core/tc_entity_pool.h"
#include "core/tc_input_component.h"
#include "core/tc_scene.h"
#include "render/tc_input_manager.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_input_manager.h"
#include "tc_input_event.h"

#include <cstdio>

namespace {

struct InputProbe {
    int mouse_buttons = 0;
    uint32_t last_source = 0;
    uint32_t last_click_count = 0;
};

InputProbe g_probe;

void record_mouse_button(tc_component*, tc_mouse_button_event* event)
{
    g_probe.mouse_buttons += 1;
    g_probe.last_source = event->source;
    g_probe.last_click_count = event->click_count;
    event->handled = true;
}

const tc_input_vtable probe_input_vtable = {
    .on_mouse_button = record_mouse_button,
};

bool require_check(bool condition, const char* message)
{
    if (!condition) {
        std::fprintf(stderr, "%s\n", message);
    }
    return condition;
}

} // namespace

int main()
{
    tc_scene_handle scene = tc_scene_new_named("viewport-input-source-test");
    if (!require_check(tc_scene_handle_valid(scene), "failed to create scene")) {
        return 1;
    }

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    if (!require_check(pool != nullptr, "scene has no entity pool")) {
        tc_scene_free(scene);
        return 1;
    }
    tc_entity_id entity = tc_entity_pool_alloc(pool, "input-entity");
    if (!require_check(tc_entity_id_valid(entity), "failed to allocate entity")) {
        tc_scene_free(scene);
        return 1;
    }
    tc_entity_pool_set_enabled(pool, entity, true);

    tc_component component;
    tc_component_init(&component, nullptr);
    if (!require_check(tc_input_capability_attach(&component, &probe_input_vtable),
                       "failed to attach input capability")) {
        tc_scene_free(scene);
        return 1;
    }
    if (!require_check(tc_component_get_input_source_mask(&component) == TC_INPUT_SOURCE_RUNTIME,
                       "input capability did not default to runtime source")) {
        tc_component_clear_capabilities(&component);
        tc_scene_free(scene);
        return 1;
    }
    tc_entity_pool_add_component(pool, entity, &component);
    if (!require_check(tc_scene_capability_count(scene, tc_input_capability_id()) == 1,
                       "input capability was not indexed by scene")) {
        tc_entity_pool_remove_component(pool, entity, &component);
        tc_component_clear_capabilities(&component);
        tc_scene_free(scene);
        return 1;
    }

    tc_viewport_handle viewport = tc_viewport_new("runtime-viewport", scene);
    if (!require_check(tc_viewport_handle_valid(viewport), "failed to create viewport")) {
        tc_entity_pool_remove_component(pool, entity, &component);
        tc_component_clear_capabilities(&component);
        tc_scene_free(scene);
        return 1;
    }
    tc_viewport_input_manager* manager = tc_viewport_input_manager_new(viewport);
    if (!require_check(manager != nullptr, "failed to create viewport input manager")) {
        tc_viewport_free(viewport);
        tc_entity_pool_remove_component(pool, entity, &component);
        tc_component_clear_capabilities(&component);
        tc_scene_free(scene);
        return 1;
    }

    tc_input_manager* input = &manager->base;
    tc_input_manager_on_mouse_move(input, 10.0, 20.0);
    tc_input_manager_on_mouse_button(input, TC_MOUSE_BUTTON_LEFT, TC_INPUT_PRESS, 0, 2);
    if (g_probe.mouse_buttons != 1 || g_probe.last_source != TC_INPUT_SOURCE_RUNTIME ||
        g_probe.last_click_count != 2) {
        std::fprintf(stderr,
                     "runtime input was not delivered with runtime source: count=%d source=%u\n",
                     g_probe.mouse_buttons,
                     g_probe.last_source);
        return 1;
    }

    if (!require_check(tc_component_set_input_source_mask(&component, TC_INPUT_SOURCE_EDITOR),
                       "failed to set editor-only input source mask")) {
        return 1;
    }
    tc_input_manager_on_mouse_button(input, TC_MOUSE_BUTTON_LEFT, TC_INPUT_PRESS, 0, 1);
    if (g_probe.mouse_buttons != 1) {
        std::fprintf(stderr,
                     "runtime input reached editor-only component: count=%d\n",
                     g_probe.mouse_buttons);
        return 1;
    }

    if (!require_check(tc_component_set_input_source_mask(&component, TC_INPUT_SOURCE_RUNTIME),
                       "failed to restore runtime input source mask")) {
        return 1;
    }
    tc_input_manager_on_mouse_button(input, TC_MOUSE_BUTTON_LEFT, TC_INPUT_PRESS, 0, 1);
    if (g_probe.mouse_buttons != 2 || g_probe.last_source != TC_INPUT_SOURCE_RUNTIME) {
        std::fprintf(stderr,
                     "runtime input was not delivered after restoring runtime mask: count=%d source=%u\n",
                     g_probe.mouse_buttons,
                     g_probe.last_source);
        return 1;
    }

    tc_viewport_input_manager_free(manager);
    tc_viewport_free(viewport);
    tc_entity_pool_remove_component(pool, entity, &component);
    tc_component_clear_capabilities(&component);
    tc_scene_free(scene);
    return 0;
}
