#pragma once

#include <cstdint>
#include <cstring>
#include <span>

namespace tgfx::vulkan_detail {

    // Validate the binary envelope before copying into words or invoking
    // reflection/native code. This is not a semantic SPIR-V validator; the
    // shader toolchain owns instruction semantics and target compatibility.
    inline const char* spirv_input_error(std::span<const uint8_t> bytes) {
        constexpr size_t word_size = sizeof(uint32_t);
        constexpr size_t header_words = 5;
        if (bytes.size() % word_size != 0)
            return "SPIR-V byte size must be a multiple of four";
        if (bytes.size() <= header_words * word_size)
            return "SPIR-V requires a complete header and instruction stream";
        const auto word = [&](size_t index) {
            uint32_t value;
            std::memcpy(&value, bytes.data() + index * word_size, word_size);
            return value;
        };
        if (word(0) != 0x07230203u)
            return "SPIR-V magic is invalid or byte order is unsupported";
        const uint32_t version = word(1);
        if ((version & 0xffff00ffu) != 0x00010000u || ((version >> 8u) & 0xffu) > 6u)
            return "SPIR-V version header is invalid or unsupported";
        if (word(3) == 0 || word(3) > 0x3fffffu)
            return "SPIR-V ID bound is invalid";
        if (word(4) != 0)
            return "SPIR-V reserved schema word must be zero";

        const size_t words = bytes.size() / word_size;
        for (size_t offset = header_words; offset < words;) {
            const size_t count = word(offset) >> 16u;
            if (count == 0 || count > words - offset)
                return "SPIR-V instruction is empty or truncated";
            offset += count;
        }
        return nullptr;
    }

} // namespace tgfx::vulkan_detail
