#include "tgfx2/vulkan/internal/readback_memory.hpp"

#include <array>
#include <cstdio>
#include <vector>

namespace {
    struct Memory {
        std::array<uint8_t, 32> gpu{};
        std::array<uint8_t, 32> cpu{};
        std::vector<char> events;
        VkResult map_result = VK_SUCCESS;
        VkResult invalidate_result = VK_SUCCESS;
        bool null_map = false;
        bool mapped = false;
        bool valid = true;
        VkDeviceSize offset = 0;
        VkDeviceSize size = 0;
    };

    VkResult map(VmaAllocator allocator, VmaAllocation, void** output) {
        auto& memory = *reinterpret_cast<Memory*>(allocator);
        memory.events.push_back('m');
        memory.mapped = memory.map_result == VK_SUCCESS;
        *output = memory.null_map ? nullptr : memory.cpu.data();
        return memory.map_result;
    }

    VkResult invalidate(VmaAllocator allocator, VmaAllocation, VkDeviceSize offset, VkDeviceSize size) {
        auto& memory = *reinterpret_cast<Memory*>(allocator);
        memory.events.push_back('i');
        memory.valid &= memory.mapped;
        memory.offset = offset;
        memory.size = size;
        if (memory.invalidate_result == VK_SUCCESS) {
            // Simulate stale non-coherent host cache. Map alone never refreshes it.
            for (VkDeviceSize i = offset; i < offset + size; ++i)
                memory.cpu[i] = memory.gpu[i];
        }
        return memory.invalidate_result;
    }

    void unmap(VmaAllocator allocator, VmaAllocation) {
        auto& memory = *reinterpret_cast<Memory*>(allocator);
        memory.events.push_back('u');
        memory.valid &= memory.mapped;
        memory.mapped = false;
    }
}

int main() {
    const tgfx::vulkan_detail::ReadbackMemoryOps ops{map, invalidate, unmap};
    bool ok = true;
    for (int failure = 0; failure < 5; ++failure) {
        Memory memory;
        for (size_t i = 0; i < memory.gpu.size(); ++i)
            memory.gpu[i] = static_cast<uint8_t>(i * 7 + 3);
        memory.cpu.fill(0xcd);
        std::array<uint8_t, 9> output;
        output.fill(0xee);
        const auto original = output;
        if (failure == 2) memory.map_result = VK_ERROR_MEMORY_MAP_FAILED;
        if (failure == 3) memory.invalidate_result = VK_ERROR_OUT_OF_DEVICE_MEMORY;
        if (failure == 4) memory.null_map = true;
        const bool result = tgfx::vulkan_detail::copy_completed_readback(
            failure == 1 ? VK_TIMEOUT : VK_SUCCESS,
            reinterpret_cast<VmaAllocator>(&memory), VK_NULL_HANDLE, 5, output, ops);
        ok &= result == (failure == 0) && memory.valid && !memory.mapped;
        if (failure == 0) {
            for (size_t i = 0; i < output.size(); ++i)
                ok &= output[i] == memory.gpu[i + 5];
            ok &= memory.offset == 5 && memory.size == output.size();
            ok &= memory.events == std::vector<char>{'m', 'i', 'u'};
        } else {
            ok &= output == original;
            if (failure == 1) ok &= memory.events.empty();
            if (failure == 2) ok &= memory.events == std::vector<char>{'m'};
            if (failure == 3) ok &= memory.events == std::vector<char>{'m', 'i', 'u'};
            if (failure == 4) ok &= memory.events == std::vector<char>{'m', 'u'};
        }
    }
    if (!ok) {
        std::fprintf(stderr, "Readback memory: stale data published, invalid ordering or unbalanced mapping\n");
        return 1;
    }
    std::puts("Readback memory: non-coherent cache and completion/map/invalidate failures passed");
    return 0;
}
