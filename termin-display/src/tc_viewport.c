// tc_viewport.c - Viewport implementation using pool with generational indices
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_render_target.h"
#include "core/tc_component.h"
#include <tcbase/tc_log.h>
#include <stdlib.h>
#include <string.h>

#define MAX_VIEWPORTS 256
#define INITIAL_POOL_CAPACITY 16

struct tc_viewport {
    uint32_t generation;
    bool alive;
    char* name;
    tc_render_target_handle render_target;
    float rect[4];
    int pixel_rect[4];
    int depth;
    bool enabled;
    char* input_mode;
    bool block_input_in_editor;
    char* managed_by;
    tc_entity_handle internal_entities;
    tc_input_manager* input_manager;
    tc_viewport_handle display_prev;
    tc_viewport_handle display_next;
    // Own scene storage — viewport no longer proxies scene through
    // render target. Detach is now ordering-independent.
    tc_scene_handle scene;
};

typedef struct {
    tc_viewport* items;
    uint32_t* free_stack;
    size_t free_count;
    size_t capacity;
    size_t count;
} ViewportPool;

static ViewportPool* g_pool = NULL;

static char* tc_strdup_local(const char* s) {
    if (s == NULL) return NULL;
    size_t len = strlen(s) + 1;
    char* copy = (char*)malloc(len);
    if (copy) memcpy(copy, s, len);
    return copy;
}

static void tc_viewport_strset(char** dest, const char* src) {
    free(*dest);
    *dest = tc_strdup_local(src);
}

static void viewport_init_empty(tc_viewport* vp, uint32_t generation) {
    if (!vp) return;
    memset(vp, 0, sizeof(*vp));
    vp->generation = generation;
    vp->render_target = TC_RENDER_TARGET_HANDLE_INVALID;
    vp->scene = TC_SCENE_HANDLE_INVALID;
    vp->internal_entities = TC_ENTITY_HANDLE_INVALID;
    vp->display_prev = TC_VIEWPORT_HANDLE_INVALID;
    vp->display_next = TC_VIEWPORT_HANDLE_INVALID;
}

static void viewport_free_strings(tc_viewport* vp) {
    if (!vp) return;
    free(vp->name);
    free(vp->input_mode);
    free(vp->managed_by);
    vp->name = NULL;
    vp->input_mode = NULL;
    vp->managed_by = NULL;
}

static tc_viewport* viewport_get_alive(tc_viewport_handle h) {
    if (!g_pool) return NULL;
    if (h.index >= g_pool->capacity) return NULL;
    tc_viewport* vp = &g_pool->items[h.index];
    if (!vp->alive || vp->generation != h.generation) return NULL;
    return vp;
}

void tc_viewport_pool_init(void) {
    if (g_pool) {
        tc_log_warn("[tc_viewport_pool] already initialized");
        return;
    }

    g_pool = (ViewportPool*)calloc(1, sizeof(ViewportPool));
    if (!g_pool) {
        tc_log_error("[tc_viewport_pool] allocation failed");
        return;
    }

    size_t cap = INITIAL_POOL_CAPACITY;

    g_pool->items = (tc_viewport*)calloc(cap, sizeof(tc_viewport));
    g_pool->free_stack = (uint32_t*)malloc(cap * sizeof(uint32_t));

    if (!g_pool->items || !g_pool->free_stack) {
        tc_log_error("[tc_viewport_pool] storage allocation failed");
        free(g_pool->items);
        free(g_pool->free_stack);
        free(g_pool);
        g_pool = NULL;
        return;
    }

    for (size_t i = 0; i < cap; i++) {
        g_pool->free_stack[i] = (uint32_t)(cap - 1 - i);
        viewport_init_empty(&g_pool->items[i], 0);
    }
    g_pool->free_count = cap;
    g_pool->capacity = cap;
    g_pool->count = 0;
}

void tc_viewport_pool_shutdown(void) {
    if (!g_pool) {
        tc_log_warn("[tc_viewport_pool] not initialized");
        return;
    }

    for (size_t i = 0; i < g_pool->capacity; i++) {
        if (g_pool->items[i].alive) {
            viewport_free_strings(&g_pool->items[i]);
        }
    }

    free(g_pool->items);
    free(g_pool->free_stack);
    free(g_pool);
    g_pool = NULL;
}

static void pool_grow(void) {
    size_t old_cap = g_pool->capacity;
    size_t new_cap = old_cap * 2;
    if (new_cap > MAX_VIEWPORTS) new_cap = MAX_VIEWPORTS;
    if (new_cap <= old_cap) {
        tc_log_error("[tc_viewport_pool] max capacity reached");
        return;
    }

    tc_viewport* new_items = (tc_viewport*)malloc(new_cap * sizeof(tc_viewport));
    uint32_t* new_free_stack = (uint32_t*)malloc(new_cap * sizeof(uint32_t));
    if (!new_items || !new_free_stack) {
        tc_log_error("[tc_viewport_pool] grow allocation failed");
        free(new_items);
        free(new_free_stack);
        return;
    }

    memcpy(new_items, g_pool->items, old_cap * sizeof(tc_viewport));
    memcpy(new_free_stack, g_pool->free_stack, g_pool->free_count * sizeof(uint32_t));
    free(g_pool->items);
    free(g_pool->free_stack);
    g_pool->items = new_items;
    g_pool->free_stack = new_free_stack;
    for (size_t i = old_cap; i < new_cap; i++) {
        viewport_init_empty(&g_pool->items[i], 0);
    }

    for (size_t i = old_cap; i < new_cap; i++) {
        g_pool->free_stack[g_pool->free_count++] = (uint32_t)(new_cap - 1 - (i - old_cap));
    }

    g_pool->capacity = new_cap;
}

static inline bool handle_alive(tc_viewport_handle h) {
    return viewport_get_alive(h) != NULL;
}

bool tc_viewport_pool_alive(tc_viewport_handle h) {
    return handle_alive(h);
}

bool tc_viewport_alive(tc_viewport_handle h) {
    return handle_alive(h);
}

tc_viewport_handle tc_viewport_pool_alloc(const char* name) {
    if (!g_pool) {
        tc_viewport_pool_init();
        if (!g_pool) {
            return TC_VIEWPORT_HANDLE_INVALID;
        }
    }

    if (g_pool->free_count == 0) {
        pool_grow();
        if (g_pool->free_count == 0) {
            tc_log_error("[tc_viewport_pool] no free slots");
            return TC_VIEWPORT_HANDLE_INVALID;
        }
    }

    uint32_t idx = g_pool->free_stack[--g_pool->free_count];
    tc_viewport* vp = &g_pool->items[idx];
    uint32_t gen = vp->generation;

    viewport_free_strings(vp);
    viewport_init_empty(vp, gen);
    vp->alive = true;
    vp->name = tc_strdup_local(name);
    vp->render_target = TC_RENDER_TARGET_HANDLE_INVALID;
    vp->scene = TC_SCENE_HANDLE_INVALID;
    vp->rect[0] = 0.0f;
    vp->rect[1] = 0.0f;
    vp->rect[2] = 1.0f;
    vp->rect[3] = 1.0f;
    vp->pixel_rect[0] = 0;
    vp->pixel_rect[1] = 0;
    vp->pixel_rect[2] = 1;
    vp->pixel_rect[3] = 1;
    vp->depth = 0;
    vp->enabled = true;
    vp->input_mode = tc_strdup_local("simple");
    vp->block_input_in_editor = false;
    vp->managed_by = NULL;
    vp->input_manager = NULL;
    vp->internal_entities = TC_ENTITY_HANDLE_INVALID;
    vp->display_prev = TC_VIEWPORT_HANDLE_INVALID;
    vp->display_next = TC_VIEWPORT_HANDLE_INVALID;
    g_pool->count++;

    tc_viewport_handle h = { idx, gen };
    return h;
}

void tc_viewport_pool_free(tc_viewport_handle h) {
    if (!handle_alive(h)) return;
    uint32_t idx = h.index;
    tc_viewport* vp = &g_pool->items[idx];

    viewport_free_strings(vp);

    uint32_t next_generation = vp->generation + 1;
    viewport_init_empty(vp, next_generation);
    g_pool->free_stack[g_pool->free_count++] = idx;
    g_pool->count--;
}

void tc_viewport_pool_foreach(tc_viewport_pool_iter_fn callback, void* user_data) {
    if (!g_pool || !callback) return;
    for (uint32_t i = 0; i < g_pool->capacity; i++) {
        tc_viewport* vp = &g_pool->items[i];
        if (vp->alive) {
            tc_viewport_handle h = { i, vp->generation };
            if (!callback(h, user_data)) {
                break;
            }
        }
    }
}

size_t tc_viewport_pool_count(void) {
    return g_pool ? g_pool->count : 0;
}

tc_viewport_handle tc_viewport_new(const char* name, tc_scene_handle scene) {
    tc_viewport_handle h = tc_viewport_pool_alloc(name);
    if (!tc_viewport_handle_valid(h)) {
        return TC_VIEWPORT_HANDLE_INVALID;
    }
    tc_viewport_set_scene(h, scene);
    return h;
}

void tc_viewport_free(tc_viewport_handle h) {
    tc_viewport_pool_free(h);
}

void tc_viewport_set_name(tc_viewport_handle h, const char* name) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    tc_viewport_strset(&vp->name, name);
}

const char* tc_viewport_get_name(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->name : NULL;
}

void tc_viewport_set_rect(tc_viewport_handle h, float x, float y, float w, float height) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->rect[0] = x;
    vp->rect[1] = y;
    vp->rect[2] = w;
    vp->rect[3] = height;
}

void tc_viewport_get_rect(tc_viewport_handle h, float* x, float* y, float* w, float* height) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    if (x) *x = vp->rect[0];
    if (y) *y = vp->rect[1];
    if (w) *w = vp->rect[2];
    if (height) *height = vp->rect[3];
}

void tc_viewport_set_pixel_rect(tc_viewport_handle h, int px, int py, int pw, int ph) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->pixel_rect[0] = px;
    vp->pixel_rect[1] = py;
    vp->pixel_rect[2] = pw;
    vp->pixel_rect[3] = ph;
}

void tc_viewport_get_pixel_rect(tc_viewport_handle h, int* px, int* py, int* pw, int* ph) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    if (px) *px = vp->pixel_rect[0];
    if (py) *py = vp->pixel_rect[1];
    if (pw) *pw = vp->pixel_rect[2];
    if (ph) *ph = vp->pixel_rect[3];
}

void tc_viewport_set_depth(tc_viewport_handle h, int depth) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->depth = depth;
}

int tc_viewport_get_depth(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->depth : 0;
}

void tc_viewport_set_layer_mask(tc_viewport_handle h, uint64_t mask) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    // Deprecated compatibility path: old callers wrote viewport.layer_mask,
    // which historically proxied to the render target. New render code uses
    // CameraComponent.layer_mask & RenderTarget.layer_mask directly.
    tc_render_target_set_layer_mask(vp->render_target, mask);
}

uint64_t tc_viewport_get_layer_mask(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return 0;
    // Deprecated compatibility path; see tc_viewport_set_layer_mask.
    return tc_render_target_get_layer_mask(vp->render_target);
}

void tc_viewport_set_enabled(tc_viewport_handle h, bool enabled) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->enabled = enabled;
}

bool tc_viewport_get_enabled(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->enabled : false;
}

void tc_viewport_set_scene(tc_viewport_handle h, tc_scene_handle scene) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->scene = scene;
    // Forward to render target for consistency when RT is set
    tc_render_target_handle rt = vp->render_target;
    if (tc_render_target_handle_valid(rt)) {
        tc_render_target_set_scene(rt, scene);
    }
}

tc_scene_handle tc_viewport_get_scene(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->scene : TC_SCENE_HANDLE_INVALID;
}

void tc_viewport_set_render_target(tc_viewport_handle h, tc_render_target_handle rt) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->render_target = rt;
    // Sync viewport's authoritative scene to the new render target
    if (tc_render_target_handle_valid(rt)) {
        tc_scene_handle vp_scene = vp->scene;
        if (tc_scene_handle_valid(vp_scene)) {
            tc_render_target_set_scene(rt, vp_scene);
        }
    }
}

tc_render_target_handle tc_viewport_get_render_target(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->render_target : TC_RENDER_TARGET_HANDLE_INVALID;
}

tc_component* tc_viewport_get_camera(tc_viewport_handle h) {
    tc_render_target_handle rt = tc_viewport_get_render_target(h);
    if (!tc_render_target_handle_valid(rt)) return NULL;
    return tc_render_target_get_camera(rt);
}

tc_pipeline_handle tc_viewport_get_pipeline(tc_viewport_handle h) {
    tc_render_target_handle rt = tc_viewport_get_render_target(h);
    if (!tc_render_target_handle_valid(rt)) return TC_PIPELINE_HANDLE_INVALID;
    return tc_render_target_get_pipeline(rt);
}

void tc_viewport_set_override_resolution(tc_viewport_handle h, bool override_resolution) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    tc_render_target_handle rt = vp->render_target;
    if (tc_render_target_handle_valid(rt)) {
        tc_render_target_set_dynamic_resolution(rt, override_resolution);
    }
}

bool tc_viewport_get_override_resolution(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return false;
    tc_render_target_handle rt = vp->render_target;
    if (tc_render_target_handle_valid(rt)) {
        return tc_render_target_get_dynamic_resolution(rt);
    }
    return false;
}

void tc_viewport_set_input_mode(tc_viewport_handle h, const char* mode) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    tc_viewport_strset(&vp->input_mode, mode ? mode : "simple");
}

const char* tc_viewport_get_input_mode(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->input_mode : NULL;
}

void tc_viewport_set_managed_by(tc_viewport_handle h, const char* pipeline_name) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    tc_viewport_strset(&vp->managed_by, pipeline_name);
}

const char* tc_viewport_get_managed_by(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->managed_by : NULL;
}

void tc_viewport_set_block_input_in_editor(tc_viewport_handle h, bool block) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->block_input_in_editor = block;
}

bool tc_viewport_get_block_input_in_editor(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->block_input_in_editor : false;
}

void tc_viewport_set_input_manager(tc_viewport_handle h, tc_input_manager* manager) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->input_manager = manager;
}

tc_input_manager* tc_viewport_get_input_manager(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->input_manager : NULL;
}

void tc_viewport_update_pixel_rect(tc_viewport_handle h, int display_width, int display_height) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    float x = vp->rect[0];
    float y = vp->rect[1];
    float w = vp->rect[2];
    float height = vp->rect[3];

    vp->pixel_rect[0] = (int)(x * display_width);
    vp->pixel_rect[1] = (int)(y * display_height);
    vp->pixel_rect[2] = (int)(w * display_width);
    vp->pixel_rect[3] = (int)(height * display_height);
}

void tc_viewport_set_internal_entities(tc_viewport_handle h, tc_entity_handle ent) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->internal_entities = ent;
}

tc_entity_handle tc_viewport_get_internal_entities(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->internal_entities : TC_ENTITY_HANDLE_INVALID;
}

bool tc_viewport_has_internal_entities(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? tc_entity_handle_valid(vp->internal_entities) : false;
}

tc_viewport_handle tc_viewport_get_display_next(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->display_next : TC_VIEWPORT_HANDLE_INVALID;
}

tc_viewport_handle tc_viewport_get_display_prev(tc_viewport_handle h) {
    tc_viewport* vp = viewport_get_alive(h);
    return vp ? vp->display_prev : TC_VIEWPORT_HANDLE_INVALID;
}

void tc_viewport_set_display_next(tc_viewport_handle h, tc_viewport_handle next) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->display_next = next;
}

void tc_viewport_set_display_prev(tc_viewport_handle h, tc_viewport_handle prev) {
    tc_viewport* vp = viewport_get_alive(h);
    if (!vp) return;
    vp->display_prev = prev;
}
