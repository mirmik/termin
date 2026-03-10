#include "core/tc_input_scene.h"

void tc_scene_foreach_input_handler(
    tc_scene_handle h,
    tc_component_iter_fn callback,
    void* user_data,
    int filter_flags
) {
    tc_scene_foreach_with_capability(h, tc_input_capability_id(), callback, user_data, filter_flags);
}
