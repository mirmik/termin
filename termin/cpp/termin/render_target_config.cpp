// render_target_config.cpp - RenderTargetConfig implementation
#include "render_target_config.hpp"
#include <tcbase/tgfx_intern_string.h>

namespace termin {

tc_render_target_config RenderTargetConfig::to_c() const {
    tc_render_target_config c;
    tc_render_target_config_init(&c);

    c.name = name.empty() ? nullptr : tgfx_intern_string(name.c_str());
    c.camera_uuid = camera_uuid.empty() ? nullptr : tgfx_intern_string(camera_uuid.c_str());
    c.width = width;
    c.height = height;
    c.pipeline_uuid = pipeline_uuid.empty() ? nullptr : tgfx_intern_string(pipeline_uuid.c_str());
    c.pipeline_name = pipeline_name.empty() ? nullptr : tgfx_intern_string(pipeline_name.c_str());
    c.layer_mask = layer_mask;
    c.enabled = enabled;

    return c;
}

RenderTargetConfig RenderTargetConfig::from_c(const tc_render_target_config* c) {
    RenderTargetConfig cfg;
    if (!c) return cfg;

    cfg.name = c->name ? c->name : "";
    cfg.camera_uuid = c->camera_uuid ? c->camera_uuid : "";
    cfg.width = c->width;
    cfg.height = c->height;
    cfg.pipeline_uuid = c->pipeline_uuid ? c->pipeline_uuid : "";
    cfg.pipeline_name = c->pipeline_name ? c->pipeline_name : "";
    cfg.layer_mask = c->layer_mask;
    cfg.enabled = c->enabled;

    return cfg;
}

} // namespace termin
