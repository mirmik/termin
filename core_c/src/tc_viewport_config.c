// tc_viewport_config.c - Viewport configuration implementation
#include "../include/tc_viewport_config.h"
#include "../include/termin_core.h"
#include <string.h>

void tc_viewport_config_init(tc_viewport_config* config) {
    if (!config) return;
    memset(config, 0, sizeof(tc_viewport_config));
    config->display_name = tc_intern_string("Main");
    config->region[0] = 0.0f;
    config->region[1] = 0.0f;
    config->region[2] = 1.0f;
    config->region[3] = 1.0f;
    config->input_mode = tc_intern_string("simple");
    config->layer_mask = 0xFFFFFFFFFFFFFFFFULL;
    config->enabled = true;
}

void tc_viewport_config_copy(tc_viewport_config* dst, const tc_viewport_config* src) {
    if (!dst || !src) return;
    dst->name = src->name ? tc_intern_string(src->name) : NULL;
    dst->display_name = src->display_name ? tc_intern_string(src->display_name) : tc_intern_string("Main");
    dst->camera_uuid = src->camera_uuid ? tc_intern_string(src->camera_uuid) : NULL;
    dst->region[0] = src->region[0];
    dst->region[1] = src->region[1];
    dst->region[2] = src->region[2];
    dst->region[3] = src->region[3];
    dst->pipeline_uuid = src->pipeline_uuid ? tc_intern_string(src->pipeline_uuid) : NULL;
    dst->pipeline_name = src->pipeline_name ? tc_intern_string(src->pipeline_name) : NULL;
    dst->depth = src->depth;
    dst->input_mode = src->input_mode ? tc_intern_string(src->input_mode) : tc_intern_string("simple");
    dst->block_input_in_editor = src->block_input_in_editor;
    dst->layer_mask = src->layer_mask;
    dst->enabled = src->enabled;
}
