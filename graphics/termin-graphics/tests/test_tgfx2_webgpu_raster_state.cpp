#include "guard_main.h"

#include <limits>

#include "tgfx2/webgpu/webgpu_raster_state.hpp"

TEST_CASE("WebGPU raster mapping preserves supported depth bias state") {
    tgfx::RasterState source;
    source.depth_bias_enabled = true;
    source.depth_bias_constant = -7.0f;
    source.depth_bias_slope = 1.25f;
    source.depth_bias_clamp = 0.5f;

    tgfx::webgpu::NativeRasterState native;
    CHECK(tgfx::webgpu::map_raster_state(source, native) == tgfx::webgpu::RasterStateError::None);
    CHECK(native.depth_bias == -7);
    CHECK(native.depth_bias_slope_scale == 1.25f);
    CHECK(native.depth_bias_clamp == 0.5f);
}

TEST_CASE("WebGPU raster mapping zeros disabled depth bias state") {
    tgfx::RasterState source;
    source.depth_bias_constant = 8.0f;
    source.depth_bias_slope = 2.0f;
    source.depth_bias_clamp = 1.0f;

    tgfx::webgpu::NativeRasterState native{13, 13.0f, 13.0f};
    CHECK(tgfx::webgpu::map_raster_state(source, native) == tgfx::webgpu::RasterStateError::None);
    CHECK(native.depth_bias == 0);
    CHECK(native.depth_bias_slope_scale == 0.0f);
    CHECK(native.depth_bias_clamp == 0.0f);
}

TEST_CASE("WebGPU raster mapping rejects unsupported polygon modes") {
    tgfx::RasterState source;
    tgfx::webgpu::NativeRasterState native;

    source.polygon_mode = tgfx::PolygonMode::Line;
    CHECK(tgfx::webgpu::map_raster_state(source, native) ==
          tgfx::webgpu::RasterStateError::UnsupportedPolygonMode);

    source.polygon_mode = tgfx::PolygonMode::Point;
    CHECK(tgfx::webgpu::map_raster_state(source, native) ==
          tgfx::webgpu::RasterStateError::UnsupportedPolygonMode);
}

TEST_CASE("WebGPU raster mapping rejects depth bias values it cannot represent") {
    tgfx::RasterState source;
    source.depth_bias_enabled = true;
    tgfx::webgpu::NativeRasterState native;

    source.depth_bias_constant = 0.5f;
    CHECK(tgfx::webgpu::map_raster_state(source, native) ==
          tgfx::webgpu::RasterStateError::FractionalDepthBiasConstant);

    source.depth_bias_constant = std::numeric_limits<float>::infinity();
    CHECK(tgfx::webgpu::map_raster_state(source, native) == tgfx::webgpu::RasterStateError::NonFiniteDepthBias);

    source.depth_bias_constant = 2147483648.0f;
    CHECK(tgfx::webgpu::map_raster_state(source, native) ==
          tgfx::webgpu::RasterStateError::DepthBiasConstantOutOfRange);

    source.depth_bias_constant = 0.0f;
    source.depth_bias_slope = std::numeric_limits<float>::quiet_NaN();
    CHECK(tgfx::webgpu::map_raster_state(source, native) == tgfx::webgpu::RasterStateError::NonFiniteDepthBias);
}
