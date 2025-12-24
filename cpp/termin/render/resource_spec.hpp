#pragma once

#include <string>
#include <optional>
#include <array>

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

    ResourceSpec() = default;

    ResourceSpec(
        std::string resource_,
        std::string resource_type_ = "fbo",
        std::optional<std::pair<int, int>> size_ = std::nullopt,
        std::optional<std::array<double, 4>> clear_color_ = std::nullopt,
        std::optional<float> clear_depth_ = std::nullopt,
        std::optional<std::string> format_ = std::nullopt,
        int samples_ = 1
    ) : resource(std::move(resource_)),
        resource_type(std::move(resource_type_)),
        size(std::move(size_)),
        clear_color(std::move(clear_color_)),
        clear_depth(std::move(clear_depth_)),
        format(std::move(format_)),
        samples(samples_) {}
};

} // namespace termin
