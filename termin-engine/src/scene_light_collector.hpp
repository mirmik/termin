#pragma once

#include <vector>

#include <termin/lighting/light.hpp>

extern "C" {
#include <core/tc_scene_pool.h>
}

namespace termin::rendering_manager_detail {

std::vector<Light> collect_lights(tc_scene_handle scene);

} // namespace termin::rendering_manager_detail
