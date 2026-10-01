#pragma once

#include "tgfx/resources/tc_texture.h"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/tgfx2_api.h"

namespace tgfx {

    // Convert the authoritative CPU sampler state at the graphics boundary.
    // Invalid state is logged and leaves out unchanged; native device limits
    // are checked when the resulting descriptor creates a sampler.
    TGFX2_API bool tc_sampler_to_tgfx2(const tc_sampler_desc& source, SamplerDesc& out);

} // namespace tgfx
