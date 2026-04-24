// tc_inspect_context.h - Adapter-level runtime context helpers for inspect/kind.
#ifndef TC_INSPECT_CONTEXT_H
#define TC_INSPECT_CONTEXT_H

#include "core/tc_scene_pool.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_scene_inspect_context {
    tc_scene_handle scene;
} tc_scene_inspect_context;

static inline tc_scene_inspect_context tc_scene_inspect_context_make(tc_scene_handle scene) {
    tc_scene_inspect_context ctx;
    ctx.scene = scene;
    return ctx;
}

static inline tc_scene_handle tc_scene_inspect_context_scene(const void* context) {
    if (!context) return TC_SCENE_HANDLE_INVALID;
    const tc_scene_inspect_context* ctx = (const tc_scene_inspect_context*)context;
    return ctx->scene;
}

#ifdef __cplusplus
}
#endif

#endif // TC_INSPECT_CONTEXT_H
