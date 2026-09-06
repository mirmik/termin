#include "tgfx2/vulkan/vulkan_render_device.hpp"

#include <cstdio>
#include <cstring>
#include <exception>
#include <stdexcept>
#include <utility>
#include <vector>

int main() {
    // Minimal SPIR-V 1.0 compute module. No compiler or GPU submission is needed.
    const uint32_t words[] = {
        0x07230203, 0x00010000, 0, 5, 0,
        0x00020011, 1,                       // OpCapability Shader
        0x0003000e, 0, 1,                    // OpMemoryModel Logical GLSL450
        0x0005000f, 5, 3, 0x6e69616d, 0,     // OpEntryPoint GLCompute %3 "main"
        0x00060010, 3, 17, 1, 1, 1,          // OpExecutionMode LocalSize
        0x00020013, 1,                       // %1 = OpTypeVoid
        0x00030021, 2, 1,                    // %2 = OpTypeFunction %1
        0x00050036, 1, 3, 0, 2,              // %3 = OpFunction %1 None %2
        0x000200f8, 4,                       // %4 = OpLabel
        0x000100fd,                          // OpReturn
        0x00010038,                          // OpFunctionEnd
    };
    std::vector<uint8_t> valid(sizeof(words));
    std::memcpy(valid.data(), words, sizeof(words));
    try {
        tgfx::VulkanDeviceCreateInfo info;
        tgfx::VulkanRenderDevice device(info);
        tgfx::ShaderDesc desc;
        desc.stage = tgfx::ShaderStage::Compute;
        desc.debug_name = "shader-input-regression";
        auto rejects = [&](const std::vector<uint8_t>& bytes) {
            desc.bytecode = bytes;
            try {
                const auto handle = device.create_shader(desc);
                if (handle) {
                    device.destroy(handle);
                    std::fprintf(stderr, "Malformed shader unexpectedly accepted (%zu bytes)\n", bytes.size());
                    return false;
                }
                return true;
            } catch (const std::runtime_error&) {
                return true;
            }
        };
        for (size_t length = 0; length < 24; ++length) {
            if (!rejects({valid.begin(), valid.begin() + length}))
                return 1;
        }
        for (size_t length = valid.size() - 3; length < valid.size(); ++length) {
            if (!rejects({valid.begin(), valid.begin() + length}))
                return 1;
        }
        for (const auto [index, value] : std::vector<std::pair<size_t, uint32_t>>{
                 {0, 0}, {1, 0x00010001}, {3, 0}, {4, 1}, {5, 0x00000011}, {5, 0xffff0011}}) {
            auto invalid = valid;
            std::memcpy(invalid.data() + index * sizeof(uint32_t), &value, sizeof(value));
            if (!rejects(invalid))
                return 1;
        }
        desc.bytecode = valid;
        const auto shader = device.create_shader(desc);
        if (!shader)
            return 1;
        device.destroy(shader);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Shader input regression failed: %s\n", e.what());
        return 1;
    }
    return 0;
}
