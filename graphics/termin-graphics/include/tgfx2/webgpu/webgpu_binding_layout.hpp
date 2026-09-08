#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "tgfx2/backend_binding_plan.hpp"
#include "tgfx2/tgfx2_api.h"

namespace tgfx::webgpu {

    enum class TextureSampleType : uint8_t {
        Undefined,
        Float,
        UnfilterableFloat,
        Depth,
        Sint,
        Uint,
    };

    enum class ResourceAccess : uint8_t {
        Undefined,
        ReadOnly,
        WriteOnly,
        ReadWrite,
    };

    enum class SamplerKind : uint8_t {
        None,
        Filtering,
        NonFiltering,
        Comparison,
    };

    enum class TextureViewAspect : uint8_t {
        Undefined,
        All,
        DepthOnly,
        StencilOnly,
    };

    enum class TextureViewDimension : uint8_t {
        Undefined,
        e1D,
        e2D,
        e2DArray,
        Cube,
        CubeArray,
        e3D,
    };

    struct LayoutEntry {
        std::string name;
        ShaderResourceKind kind = ShaderResourceKind::None;
        uint32_t stage_mask = 0;
        uint32_t binding = 0;
        uint32_t size = 0;
        bool has_sampler_binding = false;
        uint32_t sampler_binding = 0;
        TextureSampleType sample_type = TextureSampleType::Undefined;
        ResourceAccess access = ResourceAccess::Undefined;
        SamplerKind sampler_kind = SamplerKind::None;
        TextureViewAspect view_aspect = TextureViewAspect::Undefined;
        TextureViewDimension view_dimension = TextureViewDimension::Undefined;
        bool multisampled = false;

        bool operator==(const LayoutEntry&) const = default;
    };

    struct BindingLayoutParseResult {
        std::vector<LayoutEntry> entries;
        std::string error;

        explicit operator bool() const {
            return error.empty();
        }
    };

    TGFX2_API BindingLayoutParseResult parse_binding_layout(std::string_view json, std::string_view debug_name);

} // namespace tgfx::webgpu
