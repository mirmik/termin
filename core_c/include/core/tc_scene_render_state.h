// tc_scene_render_state.h - Render scene state extension (lighting, skybox, background)
#ifndef TC_SCENE_RENDER_STATE_H
#define TC_SCENE_RENDER_STATE_H

#include "core/tc_scene_pool.h"
#include "core/tc_scene_lighting.h"
#include "core/tc_scene_skybox.h"

#ifdef __cplusplus
extern "C" {
#endif

// Builtin scene extension type id for render state.
#define TC_SCENE_EXT_TYPE_RENDER_STATE UINT64_C(0x72656e6465727374)

typedef struct tc_scene_render_state {
    tc_scene_lighting lighting;
    tc_scene_skybox skybox;
    float background_color[4];
} tc_scene_render_state;

// Register builtin render-state extension type in scene-extension registry.
// Safe to call multiple times.
TC_API void tc_scene_render_state_extension_init(void);

// Access render-state extension instance from scene.
TC_API tc_scene_render_state* tc_scene_render_state_get(tc_scene_handle scene);

// Ensure render-state extension is attached to scene.
TC_API bool tc_scene_render_state_ensure(tc_scene_handle scene);

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_RENDER_STATE_H
