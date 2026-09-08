#include "guard_main.h"

#include "tgfx2/webgpu/webgpu_primitive_state.hpp"

TEST_CASE("WebGPU primitive state maps indexed and non-indexed strip contracts") {
    using namespace tgfx;
    using namespace tgfx::webgpu;

    struct Case {
        PrimitiveTopology topology;
        StripIndexFormat source;
        NativeStripIndexFormat expected;
    };
    constexpr Case cases[] = {
        {PrimitiveTopology::LineStrip, StripIndexFormat::Undefined, NativeStripIndexFormat::Undefined},
        {PrimitiveTopology::TriangleStrip, StripIndexFormat::Undefined, NativeStripIndexFormat::Undefined},
        {PrimitiveTopology::LineStrip, StripIndexFormat::Uint16, NativeStripIndexFormat::Uint16},
        {PrimitiveTopology::LineStrip, StripIndexFormat::Uint32, NativeStripIndexFormat::Uint32},
        {PrimitiveTopology::TriangleStrip, StripIndexFormat::Uint16, NativeStripIndexFormat::Uint16},
        {PrimitiveTopology::TriangleStrip, StripIndexFormat::Uint32, NativeStripIndexFormat::Uint32},
    };

    for (const Case& test : cases) {
        NativePrimitiveState native;
        CHECK(map_primitive_state(test.topology, test.source, native) == PrimitiveStateError::None);
        CHECK(native.strip_index_format == test.expected);
    }
}

TEST_CASE("WebGPU primitive state rejects strip formats on list pipelines") {
    using namespace tgfx;
    using namespace tgfx::webgpu;

    NativePrimitiveState native;
    CHECK(map_primitive_state(PrimitiveTopology::LineList, StripIndexFormat::Uint16, native) ==
          PrimitiveStateError::StripIndexFormatOnListTopology);
    CHECK(map_primitive_state(PrimitiveTopology::TriangleList, StripIndexFormat::Uint32, native) ==
          PrimitiveStateError::StripIndexFormatOnListTopology);
}
