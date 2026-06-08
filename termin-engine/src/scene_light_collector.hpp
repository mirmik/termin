#pragma once

#include "termin/render/render_engine.hpp"

namespace termin::rendering_manager_detail {

std::vector<Light> collect_lights(tc_scene_handle scene);

} // namespace termin::rendering_manager_detail
