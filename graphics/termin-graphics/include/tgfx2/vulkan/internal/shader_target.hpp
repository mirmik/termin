#pragma once

#include <vulkan/vulkan.h>

namespace tgfx::vulkan_detail {
    struct ShaderTarget {
        uint32_t vulkan;
        uint32_t spirv;
    };

    // Core baselines only. Optional SPIR-V environment extensions do not
    // silently change the artifact contract of a compatibility device.
    inline constexpr ShaderTarget shader_target(uint32_t api) {
        if (api >= VK_API_VERSION_1_3) return {VK_API_VERSION_1_3, 0x00010600};
        if (api >= VK_API_VERSION_1_2) return {VK_API_VERSION_1_2, 0x00010500};
        if (api >= VK_API_VERSION_1_1) return {VK_API_VERSION_1_1, 0x00010300};
        return {VK_API_VERSION_1_0, 0x00010000};
    }
}
