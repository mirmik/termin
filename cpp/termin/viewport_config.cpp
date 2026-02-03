// viewport_config.cpp - ViewportConfig implementation
#include "viewport_config.hpp"

extern "C" {
#include "termin_core.h"
}

namespace termin {

tc_viewport_config ViewportConfig::to_c() const {
    tc_viewport_config c;
    tc_viewport_config_init(&c);

    c.name = name.empty() ? nullptr : tc_intern_string(name.c_str());
    c.display_name = display_name.empty() ? nullptr : tc_intern_string(display_name.c_str());
    c.camera_uuid = camera_uuid.empty() ? nullptr : tc_intern_string(camera_uuid.c_str());
    c.region[0] = region_x;
    c.region[1] = region_y;
    c.region[2] = region_w;
    c.region[3] = region_h;
    c.pipeline_uuid = pipeline_uuid.empty() ? nullptr : tc_intern_string(pipeline_uuid.c_str());
    c.pipeline_name = pipeline_name.empty() ? nullptr : tc_intern_string(pipeline_name.c_str());
    c.depth = depth;
    c.input_mode = input_mode.empty() ? nullptr : tc_intern_string(input_mode.c_str());
    c.block_input_in_editor = block_input_in_editor;
    c.layer_mask = layer_mask;
    c.enabled = enabled;

    return c;
}

ViewportConfig ViewportConfig::from_c(const tc_viewport_config* c) {
    ViewportConfig cfg;
    if (!c) return cfg;

    cfg.name = c->name ? c->name : "";
    cfg.display_name = c->display_name ? c->display_name : "Main";
    cfg.camera_uuid = c->camera_uuid ? c->camera_uuid : "";
    cfg.region_x = c->region[0];
    cfg.region_y = c->region[1];
    cfg.region_w = c->region[2];
    cfg.region_h = c->region[3];
    cfg.pipeline_uuid = c->pipeline_uuid ? c->pipeline_uuid : "";
    cfg.pipeline_name = c->pipeline_name ? c->pipeline_name : "";
    cfg.depth = c->depth;
    cfg.input_mode = c->input_mode ? c->input_mode : "simple";
    cfg.block_input_in_editor = c->block_input_in_editor;
    cfg.layer_mask = c->layer_mask;
    cfg.enabled = c->enabled;

    return cfg;
}

} // namespace termin
