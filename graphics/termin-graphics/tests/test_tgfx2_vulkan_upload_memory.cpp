#include "tgfx2/vulkan/internal/upload_memory.hpp"

#include <array>
#include <cstdio>
#include <vector>

namespace {
    struct Memory {
        std::array<uint8_t, 32> bytes{};
        std::vector<char> events;
        VkResult create_result = VK_SUCCESS;
        VkResult map_result = VK_SUCCESS;
        bool null_map = false;
        bool mapped = false;
        bool valid = true;
    };

    VkResult create_buffer(VmaAllocator allocator,
                           const VkBufferCreateInfo*,
                           const VmaAllocationCreateInfo*,
                           VkBuffer* buffer,
                           VmaAllocation* allocation,
                           VmaAllocationInfo*) {
        auto& memory = *reinterpret_cast<Memory*>(allocator);
        memory.events.push_back('c');
        if (memory.create_result == VK_SUCCESS) {
            *buffer = reinterpret_cast<VkBuffer>(&memory);
            *allocation = reinterpret_cast<VmaAllocation>(&memory);
        }
        return memory.create_result;
    }

    VkResult map(VmaAllocator allocator, VmaAllocation, void** output) {
        auto& memory = *reinterpret_cast<Memory*>(allocator);
        memory.events.push_back('m');
        memory.mapped = memory.map_result == VK_SUCCESS;
        *output = memory.null_map ? nullptr : memory.bytes.data();
        return memory.map_result;
    }

    void unmap(VmaAllocator allocator, VmaAllocation) {
        auto& memory = *reinterpret_cast<Memory*>(allocator);
        memory.events.push_back('u');
        memory.valid &= memory.mapped;
        memory.mapped = false;
    }

    void destroy_buffer(VmaAllocator allocator, VkBuffer, VmaAllocation) {
        auto& memory = *reinterpret_cast<Memory*>(allocator);
        memory.events.push_back('d');
        memory.valid &= !memory.mapped;
    }

    bool exercise(VkResult create_result, VkResult map_result, bool null_map) {
        Memory memory;
        memory.bytes.fill(0xcd);
        memory.create_result = create_result;
        memory.map_result = map_result;
        memory.null_map = null_map;
        const auto original = memory.bytes;
        const std::array<uint8_t, 5> source{1, 3, 5, 7, 9};
        VkBuffer buffer = VK_NULL_HANDLE;
        VmaAllocation allocation = VK_NULL_HANDLE;
        VkBufferCreateInfo buffer_info{};
        buffer_info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
        buffer_info.size = source.size();
        VmaAllocationCreateInfo allocation_info{};
        const tgfx::vulkan_detail::UploadMemoryOps ops{create_buffer, map, unmap, destroy_buffer};

        const bool result = tgfx::vulkan_detail::create_and_fill_upload_buffer(
            reinterpret_cast<VmaAllocator>(&memory),
            buffer_info,
            allocation_info,
            source,
            buffer,
            allocation,
            ops);
        const bool expected = create_result == VK_SUCCESS && map_result == VK_SUCCESS && !null_map;
        bool ok = result == expected && memory.valid && !memory.mapped;
        if (expected) {
            for (size_t i = 0; i < source.size(); ++i)
                ok &= memory.bytes[i] == source[i];
            ok &= memory.events == std::vector<char>{'c', 'm', 'u'};
            // The caller owns a successful staging allocation.
            ops.destroy_buffer(reinterpret_cast<VmaAllocator>(&memory), buffer, allocation);
        } else {
            ok &= memory.bytes == original && buffer == VK_NULL_HANDLE && allocation == VK_NULL_HANDLE;
            if (create_result != VK_SUCCESS)
                ok &= memory.events == std::vector<char>{'c'};
            else if (map_result != VK_SUCCESS)
                ok &= memory.events == std::vector<char>{'c', 'm', 'd'};
            else
                ok &= memory.events == std::vector<char>{'c', 'm', 'u', 'd'};
        }
        return ok;
    }
}

int main() {
    const bool ok = exercise(VK_SUCCESS, VK_SUCCESS, false) &&
                    exercise(VK_ERROR_OUT_OF_DEVICE_MEMORY, VK_SUCCESS, false) &&
                    exercise(VK_SUCCESS, VK_ERROR_MEMORY_MAP_FAILED, false) &&
                    exercise(VK_SUCCESS, VK_SUCCESS, true);
    if (!ok) {
        std::fprintf(stderr, "Vulkan upload allocation/map failure contract failed\n");
        return 1;
    }
    std::puts("Vulkan upload allocation/map failure contract passed");
    return 0;
}
