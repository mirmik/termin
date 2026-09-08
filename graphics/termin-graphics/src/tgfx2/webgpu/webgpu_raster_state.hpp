#pragma once

#include <cmath>
#include <cstdint>
#include <limits>
#include <type_traits>

#include "tgfx2/render_state.hpp"

namespace tgfx::webgpu {

    enum class RasterStateError {
        None,
        UnsupportedPolygonMode,
        NonFiniteDepthBias,
        FractionalDepthBiasConstant,
        DepthBiasConstantOutOfRange,
    };

    // Backend-neutral form of the fields accepted by WebGPU's
    // DepthStencilState. Keeping the conversion independent from Dawn makes
    // the lossy float-to-i32 boundary explicit and unit-testable on native CI.
    struct NativeRasterState {
        int32_t depth_bias = 0;
        float depth_bias_slope_scale = 0.0f;
        float depth_bias_clamp = 0.0f;
    };

    inline RasterStateError map_raster_state(const RasterState& source, NativeRasterState& destination) noexcept {
        destination = {};

        if (source.polygon_mode != PolygonMode::Fill) {
            return RasterStateError::UnsupportedPolygonMode;
        }
        if (!source.depth_bias_enabled) {
            return RasterStateError::None;
        }
        if (!std::isfinite(source.depth_bias_constant) || !std::isfinite(source.depth_bias_slope) ||
            !std::isfinite(source.depth_bias_clamp)) {
            return RasterStateError::NonFiniteDepthBias;
        }
        if (std::trunc(source.depth_bias_constant) != source.depth_bias_constant) {
            return RasterStateError::FractionalDepthBiasConstant;
        }
        const double depth_bias_constant = static_cast<double>(source.depth_bias_constant);
        if (depth_bias_constant < static_cast<double>(std::numeric_limits<int32_t>::min()) ||
            depth_bias_constant > static_cast<double>(std::numeric_limits<int32_t>::max())) {
            return RasterStateError::DepthBiasConstantOutOfRange;
        }

        destination.depth_bias = static_cast<int32_t>(source.depth_bias_constant);
        destination.depth_bias_slope_scale = source.depth_bias_slope;
        destination.depth_bias_clamp = source.depth_bias_clamp;
        return RasterStateError::None;
    }

    static_assert(std::is_standard_layout_v<NativeRasterState>);

} // namespace tgfx::webgpu
