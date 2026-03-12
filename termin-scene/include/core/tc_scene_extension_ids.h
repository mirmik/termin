// tc_scene_extension_ids.h - Canonical builtin scene extension slot ids
#ifndef TC_SCENE_EXTENSION_IDS_H
#define TC_SCENE_EXTENSION_IDS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TC_SCENE_EXT_TYPE_RENDER_MOUNT UINT64_C(0)
#define TC_SCENE_EXT_TYPE_RENDER_STATE UINT64_C(1)
#define TC_SCENE_EXT_TYPE_COLLISION_WORLD UINT64_C(2)

#define TC_SCENE_EXT_TYPE_COUNT 3

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_EXTENSION_IDS_H
