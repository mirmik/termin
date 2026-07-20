#pragma once

#include "termin/render/rendering_manager.hpp"

namespace termin::rendering_manager_detail {

void present_display(RenderingManager& manager, tc_display_handle display);

} // namespace termin::rendering_manager_detail
