#pragma once

#include "termin/render/render_pipeline.hpp"

namespace tgfx {
    class IRenderDevice;
}

namespace termin::rendering_manager_detail {

    tc_pipeline_handle make_default_pipeline(const tgfx::IRenderDevice* device);

} // namespace termin::rendering_manager_detail
