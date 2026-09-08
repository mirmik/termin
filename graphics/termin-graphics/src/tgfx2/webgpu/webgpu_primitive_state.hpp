#pragma once

#include <type_traits>

#include "tgfx2/enums.hpp"

namespace tgfx::webgpu {

    enum class PrimitiveStateError {
        None,
        StripIndexFormatOnListTopology,
    };

    enum class NativeStripIndexFormat {
        Undefined,
        Uint16,
        Uint32,
    };

    struct NativePrimitiveState {
        NativeStripIndexFormat strip_index_format = NativeStripIndexFormat::Undefined;
    };

    inline PrimitiveStateError map_primitive_state(PrimitiveTopology topology,
                                                   StripIndexFormat strip_index_format,
                                                   NativePrimitiveState& destination) noexcept {
        destination = {};
        const bool strip = topology == PrimitiveTopology::LineStrip || topology == PrimitiveTopology::TriangleStrip;
        if (!strip && strip_index_format != StripIndexFormat::Undefined)
            return PrimitiveStateError::StripIndexFormatOnListTopology;
        if (strip_index_format == StripIndexFormat::Uint16)
            destination.strip_index_format = NativeStripIndexFormat::Uint16;
        else if (strip_index_format == StripIndexFormat::Uint32)
            destination.strip_index_format = NativeStripIndexFormat::Uint32;
        return PrimitiveStateError::None;
    }

    static_assert(std::is_standard_layout_v<NativePrimitiveState>);

} // namespace tgfx::webgpu
