// render_target_config.hpp - C++ RenderTargetConfig class
#pragma once

#include <cstdint>
#include <map>
#include <string>

extern "C" {
#include "tc_render_target_config.h"
}

namespace termin {

class RenderTargetConfig {
public:
    std::string name;
    std::string camera_uuid;
    int width = 512;
    int height = 512;
    bool dynamic_resolution = false;
    std::string color_format = "rgba16f";
    std::string depth_format = "depth32f";
    std::string pipeline_uuid;
    std::string pipeline_name;
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;
    bool enabled = true;
    std::map<std::string, std::string> pipeline_params;

    RenderTargetConfig() = default;

    tc_render_target_config to_c() const;
    static RenderTargetConfig from_c(const tc_render_target_config* c);
};

} // namespace termin
