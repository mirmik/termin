// tc_scene_extension.h - Scene extension registry and per-scene instances
#ifndef TC_SCENE_EXTENSION_H
#define TC_SCENE_EXTENSION_H

#include "core/tc_scene_pool.h"
#include "tc_value.h"
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef uint64_t tc_scene_ext_type_id;

typedef struct tc_scene_ext_vtable {
    void* (*create)(tc_scene_handle scene, void* type_userdata);
    void (*destroy)(void* ext, void* type_userdata);
    void (*on_scene_update)(void* ext, double dt, void* type_userdata);
    void (*on_scene_before_render)(void* ext, void* type_userdata);
    bool (*serialize)(void* ext, tc_value* out_data, void* type_userdata);
    bool (*deserialize)(void* ext, const tc_value* in_data, void* type_userdata);
} tc_scene_ext_vtable;

// Register extension type globally.
TC_API bool tc_scene_ext_register(
    tc_scene_ext_type_id type_id,
    const char* debug_name,
    const char* persistence_key,
    const tc_scene_ext_vtable* vtable,
    void* type_userdata
);

TC_API bool tc_scene_ext_is_registered(tc_scene_ext_type_id type_id);

// Attach/detach extension instance to scene.
TC_API bool tc_scene_ext_attach(tc_scene_handle scene, tc_scene_ext_type_id type_id);
TC_API void tc_scene_ext_detach(tc_scene_handle scene, tc_scene_ext_type_id type_id);
TC_API void tc_scene_ext_detach_all(tc_scene_handle scene);

// Query extension instance from scene.
TC_API void* tc_scene_ext_get(tc_scene_handle scene, tc_scene_ext_type_id type_id);
TC_API bool tc_scene_ext_has(tc_scene_handle scene, tc_scene_ext_type_id type_id);

// Enumerate attached extension type ids for scene.
// Returns number of ids written to out_ids (up to max_count).
TC_API size_t tc_scene_ext_get_attached_types(
    tc_scene_handle scene,
    tc_scene_ext_type_id* out_ids,
    size_t max_count
);

// Serialize all attached extensions for scene into dict:
// { "<persistence_key>": <extension data dict>, ... }
TC_API tc_value tc_scene_ext_serialize_scene(tc_scene_handle scene);

// Deserialize extension data from dict:
// { "<persistence_key>": <extension data dict>, ... }
// Attaches registered extensions found in input before deserialize callback.
TC_API void tc_scene_ext_deserialize_scene(tc_scene_handle scene, const tc_value* extensions_dict);

// Internal lifecycle helpers (called from tc_init/tc_shutdown).
TC_API void tc_scene_ext_registry_init(void);
TC_API void tc_scene_ext_registry_shutdown(void);

// Internal lifecycle hooks (called from tc_scene update/render loop).
TC_API void tc_scene_ext_on_scene_update(tc_scene_handle scene, double dt);
TC_API void tc_scene_ext_on_scene_before_render(tc_scene_handle scene);

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_EXTENSION_H
