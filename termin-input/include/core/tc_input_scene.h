#ifndef TC_INPUT_SCENE_H
#define TC_INPUT_SCENE_H

#include "core/tc_scene.h"
#include "core/tc_input_component.h"

#ifdef __cplusplus
extern "C" {
#endif

TC_API void tc_scene_foreach_input_handler(
    tc_scene_handle h,
    tc_component_iter_fn callback,
    void* user_data,
    int filter_flags
);

#ifdef __cplusplus
}
#endif

#endif
