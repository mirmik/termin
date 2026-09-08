#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>

namespace tgfx::d3d11_internal {

    struct DiscardMapResult {
        uint8_t* data = nullptr;
        bool acquired = false;
    };

    struct DiscardMapOps {
        void* user = nullptr;
        DiscardMapResult (*map_discard)(void* user) = nullptr;
        void (*unmap)(void* user) = nullptr;
    };

    enum class DiscardUploadResult : uint8_t {
        Success,
        InvalidRange,
        MapFailed,
        NullMappedData,
    };

    // WRITE_DISCARD gives the driver permission to rename a dynamic buffer.
    // Rebuild the complete contents in the newly mapped storage so a partial
    // public upload preserves bytes outside the patch without writing into a
    // backing allocation that may still be in flight.
    inline DiscardUploadResult upload_discard_preserving(std::span<uint8_t> shadow,
                                                         std::span<const uint8_t> patch,
                                                         size_t offset,
                                                         const DiscardMapOps& ops) {
        if (offset > shadow.size() || patch.size() > shadow.size() - offset) {
            return DiscardUploadResult::InvalidRange;
        }
        if (!ops.map_discard || !ops.unmap) {
            return DiscardUploadResult::MapFailed;
        }

        const DiscardMapResult mapped = ops.map_discard(ops.user);
        if (!mapped.acquired) {
            return DiscardUploadResult::MapFailed;
        }
        if (!mapped.data) {
            ops.unmap(ops.user);
            return DiscardUploadResult::NullMappedData;
        }

        std::memmove(shadow.data() + offset, patch.data(), patch.size());
        std::memcpy(mapped.data, shadow.data(), shadow.size());
        ops.unmap(ops.user);
        return DiscardUploadResult::Success;
    }

} // namespace tgfx::d3d11_internal
