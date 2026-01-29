#pragma once

#include <string>
#include <optional>
#include <array>

#include "termin/render/types.hpp"

namespace termin {

/**
 * Pipeline resource specification.
 *
 * Combines resource requirements declared by render passes:
 * - Resource type (FBO, ShadowMapArray, etc.)
 * - Size (e.g., shadow map fixed 1024x1024)
 * - Clear operations (color and/or depth)
 * - Format (for future: depth texture, RGBA16F, etc.)
 *
 * If spec is not declared, defaults to viewport-sized FBO.
 */
struct ResourceSpec {
    std::string resource;
    std::string resource_type = "fbo";
    std::optional<std::pair<int, int>> size;
    std::optional<std::array<double, 4>> clear_color;
    std::optional<float> clear_depth;
    std::optional<std::string> format;
    int samples = 1;  // 1 = no MSAA, 4 = 4x MSAA

    // Viewport name for resolution context
    // Empty = offscreen (uses explicit size)
    std::string viewport_name;

    // Scale factor for viewport-relative sizing (1.0 = full resolution)
    float scale = 1.0f;

    // Texture filter mode for color attachment
    TextureFilter filter = TextureFilter::LINEAR;

    ResourceSpec() = default;

    ResourceSpec(
        std::string resource_,
        std::string resource_type_ = "fbo",
        std::optional<std::pair<int, int>> size_ = std::nullopt,
        std::optional<std::array<double, 4>> clear_color_ = std::nullopt,
        std::optional<float> clear_depth_ = std::nullopt,
        std::optional<std::string> format_ = std::nullopt,
        int samples_ = 1,
        std::string viewport_name_ = "",
        float scale_ = 1.0f,
        TextureFilter filter_ = TextureFilter::LINEAR
    ) : resource(std::move(resource_)),
        resource_type(std::move(resource_type_)),
        size(std::move(size_)),
        clear_color(std::move(clear_color_)),
        clear_depth(std::move(clear_depth_)),
        format(std::move(format_)),
        samples(samples_),
        viewport_name(std::move(viewport_name_)),
        scale(scale_),
        filter(filter_) {}
};

} // namespace termin
